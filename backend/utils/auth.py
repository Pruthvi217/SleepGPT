"""Minimal stateless session tokens (HMAC-SHA256 signed, standard library only).

Compatible with the existing JSON patient store: nothing is stored server-side. A token carries
{sub, role, exp}. role is "patient" (sub = SGP-XXXXXX) or "admin" (sub = admin username).

NOTE (inherited, unchanged): patient login is still "Patient ID only" as in the original app, so
a token proves knowledge of the ID, not a secret. Add a patient password/PIN before real use.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException

from utils.tokens import create_token, verify_token  # noqa: F401 (re-exported)

# ---------------------------- FastAPI dependencies ----------------------------

def get_session(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        return verify_token(authorization.split(" ", 1)[1].strip())
    except ValueError:
        raise HTTPException(status_code=401, detail="Session invalid or expired. Please log in again.")


def require_admin(session: dict = Depends(get_session)) -> dict:
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return session


def check_patient_access(session: dict, patient_id: str) -> None:
    """Admin may access any patient; a patient only their own ID."""
    if session["role"] == "admin":
        return
    if session["sub"] != patient_id:
        raise HTTPException(status_code=403, detail="You may only access your own records.")


def patient_access(patient_id: str, session: dict = Depends(get_session)) -> dict:
    """Dependency: patient_id is taken from the path or query string of the route."""
    check_patient_access(session, patient_id)
    return session
