"""SQLite persistence for ML analyses (standard library). patient_id is the existing SGP-XXXXXX id.

The patient master record lives in the JSON store, so SQLite cannot enforce a real FOREIGN KEY to it.
Instead: (1) a CHECK constraint enforces the exact SGP-XXXXXX format and (2) ml/service.py refuses to
insert for an ID that does not exist in the JSON store."""
from __future__ import annotations
import json, os, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path

_LOCK = threading.Lock()
_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "ml.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ml_analyses (
    id                    TEXT PRIMARY KEY,
    patient_id            TEXT NOT NULL
        CHECK (patient_id GLOB 'SGP-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    source                TEXT NOT NULL CHECK (source IN ('manual','ubidots')),
    session_id            TEXT,
    device_label          TEXT,
    status                TEXT NOT NULL CHECK (status IN ('completed','failed')),
    error_message         TEXT,
    estimated_ahi         REAL,
    detected_events       INTEGER,
    sleep_duration_hours  REAL,
    average_spo2          REAL,
    minimum_spo2          REAL,
    maximum_spo2          REAL,
    analysis_start        TEXT,
    analysis_end          TEXT,
    model_name            TEXT NOT NULL,
    model_version         TEXT NOT NULL,
    normalization_mode    TEXT NOT NULL,
    validation_status     TEXT NOT NULL DEFAULT 'unvalidated',
    config_json           TEXT,
    warnings_json         TEXT,
    events_json           TEXT,
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ml_patient_created ON ml_analyses(patient_id, created_at DESC);
"""


def db_path() -> Path:
    return Path(os.environ.get("SLEEPGPT_ML_DB") or _DEFAULT)


@contextmanager
def connect():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        con = sqlite3.connect(str(p), timeout=15)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(SCHEMA)
            yield con
            con.commit()
        finally:
            con.close()


def row_to_dict(r: sqlite3.Row, include_events: bool = False) -> dict:
    d = dict(r)
    d["warnings"] = json.loads(d.pop("warnings_json") or "[]")
    d["config"] = json.loads(d.pop("config_json") or "{}")
    ev = d.pop("events_json")
    if include_events:
        d["events"] = json.loads(ev or "[]")
    d["analysis_id"] = d["id"]
    for k in ("sampling_rate_hz", "input_samples", "analysed_samples", "windows_total", "windows_analysed", "windows_apnea"):
        d[k] = d["config"].get(k)
    d["ahi_label"] = "Estimated AHI — Unvalidated" if d.get("validation_status") == "unvalidated" else "Estimated AHI"
    d["disclaimer"] = ("Research/informational use only. Not a clinical diagnosis. Model normalization requires validation "
                       "against the original training-data statistics and real sensor data.")
    return d
