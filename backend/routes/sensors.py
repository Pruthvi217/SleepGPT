"""Future IoT sensor integration — placeholder scaffold only.

No hardware/cloud integration is implemented. This exists so the data
model and API shape are settled now: sensor readings are associated with
the same patient_id used everywhere else, and can be pushed in later
(e.g. from a cloud IoT bridge) without any other part of the app
changing.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from utils import storage
from utils.auth import patient_access, require_admin

router = APIRouter()


class SensorReading(BaseModel):
    spo2: float | None = None
    heart_rate: float | None = None
    respiration_rate: float | None = None
    snoring: bool | None = None
    body_position: str | None = None
    temperature: float | None = None
    humidity: float | None = None
    airflow: float | None = None
    timestamp: str | None = None


@router.post("/{patient_id}", dependencies=[Depends(require_admin)])
async def push_sensor_reading(patient_id: str, reading: SensorReading):
    """Placeholder ingestion endpoint for future cloud/IoT sensor data."""
    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    updated = storage.add_sensor_reading(patient_id, reading.model_dump(exclude_none=True))
    return {"patient_id": patient_id, "sensor_readings_count": len(updated["sensor_data"])}


@router.get("/{patient_id}", dependencies=[Depends(patient_access)])
async def get_sensor_readings(patient_id: str):
    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if not patient["sensor_data"]:
        return {"patient_id": patient_id, "sensor_data": [], "message": "No sensor data connected yet."}
    return {"patient_id": patient_id, "sensor_data": patient["sensor_data"]}
