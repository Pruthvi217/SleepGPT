"""
SleepGPT — Storage Layer
-------------------------
Prototype JSON-file storage for patient records.

IMPORTANT (prototype limitation): this uses a flat JSON file with a simple
in-process lock. It is NOT safe for concurrent multi-worker production
deployments and offers no encryption at rest. It is suitable only for a
single-process prototype. The public functions below (get/create/update/
list) form the storage contract — swap the implementation for MongoDB
later without changing any route or service code that calls them.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

_LOCK = threading.Lock()
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_PATIENTS_FILE = os.path.join(_DATA_DIR, "patients.json")


def _ensure_store() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.exists(_PATIENTS_FILE):
        with open(_PATIENTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _read_all() -> Dict[str, Any]:
    _ensure_store()
    with open(_PATIENTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _write_all(data: Dict[str, Any]) -> None:
    _ensure_store()
    tmp_path = _PATIENTS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, _PATIENTS_FILE)


def default_patient_record(patient_id: str, username: str) -> Dict[str, Any]:
    return {
        "patient_id": patient_id,
        "username": username,
        "answers": {},
        "results": {},
        "summary": "",
        "rag_analysis": {},
        "assessment_completed": False,
        "result_visible": False,
        "sensor_data": [],
    }


def create_patient(patient_id: str, username: str) -> Dict[str, Any]:
    with _LOCK:
        data = _read_all()
        if patient_id in data:
            raise ValueError(f"Patient ID already exists: {patient_id}")
        record = default_patient_record(patient_id, username)
        data[patient_id] = record
        _write_all(data)
        return record


def get_patient(patient_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _read_all()
        return data.get(patient_id)


def patient_exists(patient_id: str) -> bool:
    with _LOCK:
        data = _read_all()
        return patient_id in data


def update_patient(patient_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _read_all()
        if patient_id not in data:
            return None
        data[patient_id].update(fields)
        _write_all(data)
        return data[patient_id]


def set_answer(patient_id: str, question_id: int, value: Any) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _read_all()
        if patient_id not in data:
            return None
        data[patient_id]["answers"][str(question_id)] = value
        _write_all(data)
        return data[patient_id]


def list_patients() -> List[Dict[str, Any]]:
    with _LOCK:
        data = _read_all()
        return list(data.values())


def add_sensor_reading(patient_id: str, reading: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _read_all()
        if patient_id not in data:
            return None
        data[patient_id].setdefault("sensor_data", []).append(reading)
        _write_all(data)
        return data[patient_id]
