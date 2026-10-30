"""Patient registration & login."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils import storage
from utils.auth import create_token
from utils.patient_id import generate_patient_id, is_valid_patient_id_format

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    patient_id: str


@router.post("/register")
async def register(payload: RegisterRequest):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    patient_id = generate_patient_id()
    record = storage.create_patient(patient_id, username)
    return {
        "message": "Registration successful",
        "patient_id": patient_id,
        "username": record["username"],
    }


@router.post("/login")
async def login(payload: LoginRequest):
    patient_id = payload.patient_id.strip().upper()
    if not is_valid_patient_id_format(patient_id):
        raise HTTPException(status_code=400, detail="Invalid Patient ID format. Expected e.g. SGP-482931.")

    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient ID not found.")

    if not patient["assessment_completed"]:
        status = "assessment_in_progress"
    elif not patient["result_visible"]:
        status = "awaiting_review"
    else:
        status = "results_available"

    return {
        "patient_id": patient["patient_id"],
        "username": patient["username"],
        "assessment_completed": patient["assessment_completed"],
        "result_visible": patient["result_visible"],
        "status": status,
        "token": create_token(patient["patient_id"], "patient"),
    }
