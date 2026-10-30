"""ML service layer (no web framework). Used by routes/ml.py, routes/chat.py and the tests.

Data flow:  SGP-XXXXXX (JSON patient store) -> source data (manual CSV | Ubidots)
            -> ml.pipeline.run_pipeline (ONE shared pipeline) -> ml_analyses (SQLite) -> dashboards/chat."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
import numpy as np

from utils import storage
from . import config as C, db, ubidots
from .pipeline import DISCLAIMER, parse_csv, run_pipeline
from .preprocessing import SpO2ValidationError, clean_series

PATIENT_ID_NOT_FOUND = "Patient ID not found in the SleepGPT patient store."


class PatientNotFound(LookupError):
    pass


def _iso(epoch: float | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def require_patient(patient_id: str) -> dict:
    p = storage.get_patient(patient_id)
    if p is None:
        raise PatientNotFound(PATIENT_ID_NOT_FOUND)
    return p


def _insert(row: dict) -> str:
    cols = ",".join(row)
    with db.connect() as con:
        con.execute(f"INSERT INTO ml_analyses ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    return row["id"]


def analyze_and_save(patient_id: str, source: str, t, v, session_id: str | None = None,
                     device_label: str | None = None, settings: C.MLSettings | None = None) -> dict:
    """Run the shared pipeline and persist the outcome against the existing patient ID.
    On a validation failure a 'failed' row is stored (audit trail) and the error is re-raised."""
    if source not in ("manual", "ubidots"):
        raise ValueError("source must be 'manual' or 'ubidots'")
    require_patient(patient_id)
    s = settings or C.load_settings()
    base = {"id": uuid.uuid4().hex, "patient_id": patient_id, "source": source, "session_id": session_id,
            "device_label": device_label, "model_name": C.MODEL_NAME, "model_version": C.MODEL_VERSION,
            "normalization_mode": s.normalization_mode, "validation_status": "unvalidated", "created_at": _now()}
    try:
        r = run_pipeline(t, v, s)
    except SpO2ValidationError as exc:
        _insert({**base, "status": "failed", "error_message": "; ".join([str(exc)] + exc.details)[:1000]})
        raise
    row = {**base, "status": "completed", "error_message": None,
           "estimated_ahi": r["estimated_ahi"], "detected_events": r["detected_events"],
           "sleep_duration_hours": r["sleep_duration_hours"], "average_spo2": r["average_spo2"],
           "minimum_spo2": r["minimum_spo2"], "maximum_spo2": r["maximum_spo2"],
           "analysis_start": _iso(r["input_start_time"]), "analysis_end": _iso(r["input_end_time"]),
           "config_json": json.dumps(r["config"]), "warnings_json": json.dumps(r["warnings"]),
           "events_json": json.dumps(r["events"])}
    _insert(row)
    return get_analysis(patient_id, base["id"])


def analyze_csv(patient_id: str, content: bytes | str, session_id: str | None = None) -> dict:
    require_patient(patient_id)
    t, v = parse_csv(content)
    return analyze_and_save(patient_id, "manual", t, v, session_id=session_id)


def analyze_ubidots(patient_id: str, start_s: float, end_s: float, device_label: str | None = None,
                    session_id: str | None = None, http=None) -> dict:
    require_patient(patient_id)
    s = C.load_settings()
    device = (device_label or s.ubidots_device_label)
    rows = ubidots.fetch_spo2(start_s, end_s, device, s, http)
    if not rows:
        raise SpO2ValidationError("Ubidots returned no SpO2 values for this device and time range.")
    t = [r[0] for r in rows]; v = [r[1] for r in rows]
    return analyze_and_save(patient_id, "ubidots", t, v, session_id=session_id or f"{_iso(start_s)}/{_iso(end_s)}",
                            device_label=device, settings=s)


def get_analysis(patient_id: str, analysis_id: str) -> dict | None:
    with db.connect() as con:
        r = con.execute("SELECT * FROM ml_analyses WHERE id=? AND patient_id=?", (analysis_id, patient_id)).fetchone()
    return db.row_to_dict(r, include_events=True) if r else None


def latest(patient_id: str) -> dict | None:
    with db.connect() as con:
        r = con.execute("SELECT * FROM ml_analyses WHERE patient_id=? AND status='completed' "
                        "ORDER BY created_at DESC, rowid DESC LIMIT 1", (patient_id,)).fetchone()
    return db.row_to_dict(r) if r else None


def history(patient_id: str, limit: int = 50, include_failed: bool = False) -> list[dict]:
    q = "SELECT * FROM ml_analyses WHERE patient_id=?" + ("" if include_failed else " AND status='completed'")
    with db.connect() as con:
        rows = con.execute(q + " ORDER BY created_at DESC, rowid DESC LIMIT ?", (patient_id, max(1, min(limit, 500)))).fetchall()
    return [db.row_to_dict(r) for r in rows]


def latest_for_all() -> dict[str, dict]:
    with db.connect() as con:
        rows = con.execute("SELECT * FROM ml_analyses WHERE status='completed' ORDER BY created_at ASC, rowid ASC").fetchall()
    return {r["patient_id"]: db.row_to_dict(r) for r in rows}   # later rows overwrite earlier -> latest


def preview_series(t, v, max_points: int = 600) -> dict:
    """Validation + preview for the ML dashboard; never writes to the database."""
    s = C.load_settings()
    t = np.asarray(t, dtype="float64"); v = np.asarray(v, dtype="float64")
    out = {"rows_total": int(len(t)), "valid": True, "errors": [], "model_input": {
        "window_samples": C.WINDOW_SAMPLES, "sample_rate_hz": C.SAMPLE_RATE_HZ, "window_seconds": C.WINDOW_SECONDS}}
    try:
        cs = clean_series(t, v, s)
    except SpO2ValidationError as exc:
        out.update(valid=False, errors=[str(exc)] + exc.details)
        ok = np.isfinite(t) & np.isfinite(v)
        cs = None
        t, v = t[ok], v[ok]
    else:
        t, v = cs.t, cs.v
        out["dropped"] = cs.dropped
        out["median_interval_s"] = round(cs.median_interval_s, 3)
    if len(t):
        step = max(1, len(t) // max_points)
        out["chart"] = [{"t": _iso(a), "spo2": float(b)} for a, b in zip(t[::step], v[::step])]
        out["first_rows"] = [{"timestamp": _iso(a), "spo2": float(b)} for a, b in zip(t[:10], v[:10])]
        out.update(start=_iso(t[0]), end=_iso(t[-1]), duration_minutes=round(float(t[-1] - t[0]) / 60, 1),
                   average_spo2=round(float(v.mean()), 1), minimum_spo2=round(float(v.min()), 1),
                   maximum_spo2=round(float(v.max()), 1))
    return out


def preview_csv(content: bytes | str) -> dict:
    try:
        t, v = parse_csv(content)
    except SpO2ValidationError as exc:
        return {"rows_total": 0, "valid": False, "errors": [str(exc)] + exc.details}
    return preview_series(t, v)


def chat_context(patient_id: str) -> str | None:
    """Structured, factual context for the LLM (it must not compute or alter these numbers)."""
    r = latest(patient_id)
    if not r:
        return None
    return (f"Patient ID: {r['patient_id']}\nEstimated AHI (unvalidated ML estimate): {r['estimated_ahi']} events/hour\n"
            f"Detected events: {r['detected_events']}\nAnalysed duration: {r['sleep_duration_hours']} hours\n"
            f"Average SpO2: {r['average_spo2']}%\nMinimum SpO2: {r['minimum_spo2']}%\nMaximum SpO2: {r['maximum_spo2']}%\n"
            f"Source: {r['source']}\nModel: {r['model_name']} ({r['model_version']})\n"
            f"Normalization mode: {r['normalization_mode']} (validation_status: {r['validation_status']})\n"
            f"Analysed samples: {r.get('analysed_samples')} at {r.get('sampling_rate_hz')} Hz\n"
            f"Analysis window: {r['analysis_start']} to {r['analysis_end']}\nSaved at: {r['created_at']}")


def deterministic_explanation(patient_id: str) -> str:
    r = latest(patient_id)
    if not r:
        return "No ML sleep analysis is available for this patient yet."
    return (f"Your latest saved analysis ({r['created_at'][:10]}, source: {r['source']}) gave an Estimated AHI of "
            f"{r['estimated_ahi']} events per hour, based on {r['detected_events']} detected events over "
            f"{r['sleep_duration_hours']} hours of analysed SpO2 data (average {r['average_spo2']}%, minimum "
            f"{r['minimum_spo2']}%). AHI is the number of breathing-pause events per hour. This figure is an "
            f"unvalidated ML estimate from a blood-oxygen signal only; it is not a diagnosis. Please discuss it with a sleep physician.")
