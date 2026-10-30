"""Ubidots REST client (server-side only; the token never reaches the browser).

Uses the v1.6 values endpoint:
  GET {base}/api/v1.6/devices/{device}/{variable}/values/?start=<ms>&end=<ms>&page_size=<n>
  header X-Auth-Token: <BBUS-UohMphAyNl42PTob9t8zrSmQ7AXK5n>
Response: {"count":..,"next":<url|null>,"results":[{"value":..,"timestamp":<ms>,...}]}
NOT verified against a live account in development (no credentials/network available)."""
from __future__ import annotations
import os
from . import config as C


class UbidotsConfigError(RuntimeError):
    pass


class UbidotsError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def variable_labels() -> dict[str, str]:
    g = lambda k, d: (os.environ.get(k) or d).strip()
    return {"spo2": g("UBIDOTS_SPO2_VARIABLE", "spo2"),
            "heart_rate": g("UBIDOTS_HEART_RATE_VARIABLE", "heart_rate"),
            "ecg": g("UBIDOTS_ECG_VARIABLE", "ecg"),
            "respiratory_pressure": g("UBIDOTS_RESPIRATORY_PRESSURE_VARIABLE", "respiratory_pressure"),
            "temperature": g("UBIDOTS_TEMPERATURE_VARIABLE", "temperature")}


def parse_values(payload: dict) -> list[tuple[float, float | None]]:
    """Ubidots page -> [(epoch_seconds, value|None)]. Skips malformed entries."""
    out = []
    for r in (payload or {}).get("results", []):
        ts = r.get("timestamp")
        if ts is None:
            continue
        try:
            val = float(r["value"]) if r.get("value") is not None else None
        except (TypeError, ValueError):
            val = None
        out.append((float(ts) / 1000.0, val))
    return out


def fetch_variable(variable: str, start_s: float, end_s: float, device: str | None = None,
                   settings: C.MLSettings | None = None, http=None) -> list[tuple[float, float | None]]:
    s = settings or C.load_settings()
    if not s.ubidots_token:
        raise UbidotsConfigError("UBIDOTS_TOKEN is not configured on the server. Set it in backend/.env.")
    device = (device or s.ubidots_device_label).strip()
    if http is None:
        import requests as http
    url = f"{s.ubidots_base_url}/api/v1.6/devices/{device}/{variable}/values/"
    params = {"start": int(start_s * 1000), "end": int(end_s * 1000), "page_size": 1000}
    headers = {"X-Auth-Token": s.ubidots_token, "Content-Type": "application/json"}
    rows: list = []
    while url and len(rows) < s.ubidots_max_points:
        try:
            r = http.get(url, params=params, headers=headers, timeout=s.ubidots_timeout_s)
        except Exception as exc:  # network/timeout
            raise UbidotsError(f"Could not reach Ubidots: {type(exc).__name__}") from exc
        if r.status_code in (401, 403):
            raise UbidotsError("Ubidots rejected the token (check UBIDOTS_TOKEN).", 502)
        if r.status_code == 404:
            raise UbidotsError(f"Ubidots device/variable not found: {device}/{variable}.", 404)
        if r.status_code >= 400:
            raise UbidotsError(f"Ubidots returned HTTP {r.status_code}.")
        try:
            page = r.json()
        except ValueError:
            raise UbidotsError("Ubidots returned a non-JSON response.")
        rows += parse_values(page)
        url, params = page.get("next"), None   # 'next' already contains the query string
    rows.sort(key=lambda x: x[0])
    return rows


def fetch_spo2(start_s, end_s, device=None, settings=None, http=None):
    s = settings or C.load_settings()
    rows = fetch_variable(variable_labels()["spo2"], start_s, end_s, device, s, http)
    return [(t, v) for t, v in rows if v is not None]


def fetch_all_sensor_data(start_s, end_s, device=None, settings=None, http=None) -> dict:
    """All five configured variables, retained for future models (only SpO2 feeds SomnNET)."""
    s = settings or C.load_settings()
    return {name: fetch_variable(label, start_s, end_s, device, s, http) for name, label in variable_labels().items()}
