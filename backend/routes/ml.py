"""ML routes: /api/ml/*. All patient-scoped endpoints use the existing SGP-XXXXXX id and the
session-token check (patients: own id only, admin: any). Running analyses is admin-only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ml import config as C, service, ubidots
from ml.preprocessing import SpO2ValidationError
from utils import storage
from utils.auth import patient_access, require_admin

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class UbidotsRequest(BaseModel):
    start: str                    # ISO-8601 (UTC if no offset)
    end: str
    device_label: Optional[str] = None
    session_id: Optional[str] = None


def _epoch(s: str, name: str) -> float:
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(422, f"'{name}' must be an ISO-8601 date-time, e.g. 2026-10-01T22:00:00Z.")
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _range(body_start: str, body_end: str) -> tuple[float, float]:
    a, b = _epoch(body_start, "start"), _epoch(body_end, "end")
    if b <= a:
        raise HTTPException(422, "'end' must be after 'start'.")
    if b - a > 48 * 3600:
        raise HTTPException(422, "Time range is limited to 48 hours per analysis.")
    return a, b


def _guard(patient_id: str):
    try:
        service.require_patient(patient_id)
    except service.PatientNotFound as exc:
        raise HTTPException(404, str(exc))


def _handle(fn):
    try:
        return fn()
    except service.PatientNotFound as exc:
        raise HTTPException(404, str(exc))
    except SpO2ValidationError as exc:
        raise HTTPException(422, {"message": str(exc), "details": exc.details})
    except ubidots.UbidotsConfigError as exc:
        raise HTTPException(503, str(exc))
    except ubidots.UbidotsError as exc:
        raise HTTPException(exc.status, str(exc))


async def _read(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "CSV is larger than 20 MB.")
    return data


@router.get("/health")
def health():
    s = C.load_settings()
    try:
        from ml.somnnet import get_model
        get_model(s.weights_path); loaded = True
    except Exception:
        loaded = False
    return {"status": "ok" if loaded else "model_unavailable", "model_name": C.MODEL_NAME,
            "model_version": C.MODEL_VERSION, "model_loaded": loaded, "device": "cpu",
            "normalization_mode": s.normalization_mode, "validation_status": "unvalidated",
            "ubidots_configured": bool(s.ubidots_token)}


@router.get("/admin/summary")
def admin_summary(_: dict = Depends(require_admin)):
    """Latest completed analysis per patient (admin dashboard + ML dashboard patient picker)."""
    latest = service.latest_for_all()
    return {"latest": latest}


@router.get("/patients/{patient_id}/latest")
def latest(patient_id: str, _: dict = Depends(patient_access)):
    _guard(patient_id)
    return {"patient_id": patient_id, "latest": service.latest(patient_id), "disclaimer": _disc()}


@router.get("/patients/{patient_id}/history")
def history(patient_id: str, limit: int = Query(50, ge=1, le=500), include_failed: bool = False,
            session: dict = Depends(patient_access)):
    _guard(patient_id)
    if include_failed and session["role"] != "admin":
        include_failed = False
    return {"patient_id": patient_id, "history": service.history(patient_id, limit, include_failed), "disclaimer": _disc()}


@router.get("/patients/{patient_id}/analyses/{analysis_id}")
def one(patient_id: str, analysis_id: str, _: dict = Depends(patient_access)):
    a = service.get_analysis(patient_id, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found for this patient.")
    return a


@router.get("/patients/{patient_id}/sensor-data")
def sensor_data(patient_id: str, start: str, end: str, device_label: Optional[str] = None,
                _: dict = Depends(require_admin)):
    """All five Ubidots variables for a range (retained for future models; only SpO2 feeds SomnNET)."""
    _guard(patient_id)
    a, b = _range(start, end)
    def go():
        data = ubidots.fetch_all_sensor_data(a, b, device_label)
        out = {}
        for name, rows in data.items():
            step = max(1, len(rows) // 600)
            out[name] = {"count": len(rows), "points": [{"t": service._iso(t), "value": v} for t, v in rows[::step]]}
        return {"patient_id": patient_id, "device_label": device_label or C.load_settings().ubidots_device_label,
                "variables": out}
    return _handle(go)


@router.post("/patients/{patient_id}/manual/preview")
async def manual_preview(patient_id: str, file: UploadFile = File(...), _: dict = Depends(require_admin)):
    _guard(patient_id)
    return service.preview_csv(await _read(file))


@router.post("/patients/{patient_id}/manual")
async def manual_run(patient_id: str, file: UploadFile = File(...), session_id: Optional[str] = None,
                     _: dict = Depends(require_admin)):
    _guard(patient_id)
    data = await _read(file)
    return _handle(lambda: service.analyze_csv(patient_id, data, session_id or file.filename))


@router.post("/patients/{patient_id}/ubidots/preview")
def ubidots_preview(patient_id: str, body: UbidotsRequest, _: dict = Depends(require_admin)):
    _guard(patient_id)
    a, b = _range(body.start, body.end)
    def go():
        rows = ubidots.fetch_spo2(a, b, body.device_label)
        if not rows:
            return {"rows_total": 0, "valid": False, "errors": ["Ubidots returned no SpO2 values for this device and time range."]}
        return service.preview_series([r[0] for r in rows], [r[1] for r in rows])
    return _handle(go)


@router.post("/patients/{patient_id}/ubidots")
def ubidots_run(patient_id: str, body: UbidotsRequest, _: dict = Depends(require_admin)):
    _guard(patient_id)
    a, b = _range(body.start, body.end)
    return _handle(lambda: service.analyze_ubidots(patient_id, a, b, body.device_label, body.session_id))


def _disc() -> str:
    from ml.pipeline import DISCLAIMER
    return DISCLAIMER
