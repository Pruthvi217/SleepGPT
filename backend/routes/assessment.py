"""Assessment flow: start, submit answers, fetch answers/results.

All endpoints require patient_id and operate through the single
authoritative AssessmentEngine (backend/services/assessment_engine.py).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from rag import rag_engine
from services import scoring, summary
from services.assessment_engine import get_engine
from utils import storage
from utils.auth import check_patient_access, get_session, patient_access

router = APIRouter()


class AnswerRequest(BaseModel):
    patient_id: str
    question_id: int
    value: Any


def _require_patient(patient_id: str) -> dict:
    patient = storage.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient ID not found.")
    return patient


@router.get("/start", dependencies=[Depends(patient_access)])
async def start_assessment(patient_id: str = Query(...)):
    patient = _require_patient(patient_id)
    engine = get_engine(patient_id)

    if patient["assessment_completed"]:
        return {
            "completed": True,
            "message": "Assessment already completed.",
            "next_question": None,
        }

    status = engine.status()
    return status


@router.post("/answer")
async def submit_answer(payload: AnswerRequest, session: dict = Depends(get_session)):
    check_patient_access(session, payload.patient_id)
    patient = _require_patient(payload.patient_id)

    if patient["assessment_completed"]:
        raise HTTPException(status_code=400, detail="Assessment already completed for this patient.")

    engine = get_engine(payload.patient_id)
    try:
        status = engine.submit_answer(payload.question_id, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if status["completed"]:
        _finalize_assessment(payload.patient_id)
        status = {
            "completed": True,
            "next_question": None,
            "progress": status["progress"],
            "message": "Assessment submitted for review. Please wait for the administrator to release your results.",
        }

    return status


def _finalize_assessment(patient_id: str) -> None:
    patient = storage.get_patient(patient_id)
    answers = patient["answers"]

    scores = scoring.compute_all_scores(answers)
    rag_analysis = rag_engine.generate_assessment_summary(scores)
    patient_summary = summary.build_patient_summary(patient_id, scores, rag_analysis)

    storage.update_patient(
        patient_id,
        results=scores,
        rag_analysis=rag_analysis,
        summary=patient_summary,
        assessment_completed=True,
        result_visible=False,
    )


@router.get("/answers", dependencies=[Depends(patient_access)])
async def get_answers(patient_id: str = Query(...)):
    patient = _require_patient(patient_id)
    return {"patient_id": patient_id, "answers": patient["answers"]}


@router.get("/results", dependencies=[Depends(patient_access)])
async def get_results(patient_id: str = Query(...)):
    patient = _require_patient(patient_id)

    if not patient["assessment_completed"]:
        return {
            "completed": False,
            "message": "Assessment not yet completed.",
        }

    if not patient["result_visible"]:
        return {
            "completed": True,
            "result_visible": False,
            "message": "Results are awaiting administrator review.",
        }

    return {
        "completed": True,
        "result_visible": True,
        "results": patient["results"],
        "rag_analysis": patient["rag_analysis"],
        "summary": patient["summary"],
    }
