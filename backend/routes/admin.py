"""Admin dashboard routes — completely independent of the patient flow.

PROTOTYPE SECURITY NOTE: admin auth here is a simple credential check
against an env-configurable username/password, with no session/token
issued. This is acceptable only for a local prototype. Before any real
deployment, replace with proper hashed-password storage + JWT/session
auth and HTTPS.
"""

from __future__ import annotations

import os

import hmac

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from utils import storage
from utils.auth import create_token, require_admin

router = APIRouter()

_ADMIN_USERNAME = os.environ.get("SLEEPGPT_ADMIN_USERNAME", "admin")
_ADMIN_PASSWORD = os.environ.get("SLEEPGPT_ADMIN_PASSWORD", "admin123")


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(payload: AdminLoginRequest):
    ok_user = hmac.compare_digest(payload.username.encode(), _ADMIN_USERNAME.encode())
    ok_pass = hmac.compare_digest(payload.password.encode(), _ADMIN_PASSWORD.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Invalid admin credentials.")
    return {"message": "Admin login successful", "username": payload.username,
            "token": create_token(payload.username, "admin")}


@router.get("/patients", dependencies=[Depends(require_admin)])
async def list_patients():
    patients = storage.list_patients()
    return {
        "patients": [
            {
                "patient_id": p["patient_id"],
                "username": p["username"],
                "assessment_completed": p["assessment_completed"],
                "result_visible": p["result_visible"],
            }
            for p in patients
        ]
    }


@router.get("/patient/{patient_id}", dependencies=[Depends(require_admin)])
async def get_patient(patient_id: str):
    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    from ml import service as ml_service  # same SGP-XXXXXX id -> ML analyses
    return {**patient, "ml_latest": ml_service.latest(patient_id), "ml_history": ml_service.history(patient_id, 20)}


@router.post("/patient/{patient_id}/release-results", dependencies=[Depends(require_admin)])
async def release_results(patient_id: str):
    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if not patient["assessment_completed"]:
        raise HTTPException(status_code=400, detail="Cannot release results before assessment is completed.")

    updated = storage.update_patient(patient_id, result_visible=True)
    return {"patient_id": patient_id, "result_visible": updated["result_visible"]}
