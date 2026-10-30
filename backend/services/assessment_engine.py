"""
SleepGPT — Assessment Engine
------------------------------
THE single authoritative implementation of assessment/question-flow logic.
Routes must import from here rather than re-implementing this logic.

Design notes:
- Question definitions are loaded once from datasets/questions.json.
- Per-patient progress lives in the patient's persisted `answers` dict
  (backend/data/patients.json via utils/storage.py) — NOT in memory — so
  the engine is safe across process restarts and never leaks one
  patient's state into another's.
- `engines` below is a lightweight per-patient wrapper cache, matching the
  "no single global engine" requirement, but each instance is stateless
  aside from the patient_id it is bound to; the real state always comes
  from storage.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from utils import storage

_QUESTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "datasets", "questions.json",
)

_questions_cache: Optional[List[Dict[str, Any]]] = None
_questions_lock = threading.Lock()


def _load_questions() -> List[Dict[str, Any]]:
    global _questions_cache
    with _questions_lock:
        if _questions_cache is None:
            with open(_QUESTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _questions_cache = data["questions"]
        return _questions_cache


class AssessmentEngine:
    """Bound to a single patient_id. Does not hold cross-patient state."""

    def __init__(self, patient_id: str):
        self.patient_id = patient_id

    # ---------------------------------------------------------------
    # Eligibility / conditional logic
    # ---------------------------------------------------------------
    @staticmethod
    def _is_eligible(question: Dict[str, Any], answers: Dict[str, Any]) -> bool:
        show_if = question.get("show_if")
        if not show_if:
            return True
        dependency_id = str(show_if["question_id"])
        dependency_answer = answers.get(dependency_id)
        return dependency_answer == show_if["equals"]

    def _eligible_questions(self, answers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Questions currently eligible given answers so far (recomputed
        each call so conditional branches update live as answers arrive)."""
        return [q for q in _load_questions() if self._is_eligible(q, answers)]

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------
    def get_progress(self, answers: Dict[str, Any]) -> Dict[str, int]:
        eligible = self._eligible_questions(answers)
        answered = sum(1 for q in eligible if str(q["id"]) in answers)
        return {"answered": answered, "estimated_total": len(eligible)}

    def get_next_question(self, answers: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for q in self._eligible_questions(answers):
            if str(q["id"]) not in answers:
                return q
        return None

    def is_complete(self, answers: Dict[str, Any]) -> bool:
        return self.get_next_question(answers) is None

    def validate_answer(self, question: Dict[str, Any], value: Any) -> Optional[str]:
        """Returns an error message string, or None if valid."""
        qtype = question["type"]
        if value is None or value == "":
            return "Answer cannot be empty."
        if qtype == "number":
            try:
                num = float(value)
            except (TypeError, ValueError):
                return "Answer must be a number."
            if "min" in question and num < question["min"]:
                return f"Value must be at least {question['min']}."
            if "max" in question and num > question["max"]:
                return f"Value must be at most {question['max']}."
        elif qtype == "yes_no":
            if str(value) not in ("Yes", "No"):
                return "Answer must be 'Yes' or 'No'."
        elif qtype in ("choice", "scale"):
            valid_options = question.get("options", [])
            if str(value) not in valid_options:
                return f"Answer must be one of: {', '.join(valid_options)}."
        return None

    def submit_answer(self, question_id: int, value: Any) -> Dict[str, Any]:
        patient = storage.get_patient(self.patient_id)
        if patient is None:
            raise ValueError("Patient not found.")

        questions_by_id = {q["id"]: q for q in _load_questions()}
        question = questions_by_id.get(question_id)
        if question is None:
            raise ValueError("Invalid question id.")

        answers = patient["answers"]
        if not self._is_eligible(question, answers):
            raise ValueError("This question is not currently active for this patient.")

        error = self.validate_answer(question, value)
        if error:
            raise ValueError(error)

        storage.set_answer(self.patient_id, question_id, value)
        return self.status()

    def status(self) -> Dict[str, Any]:
        patient = storage.get_patient(self.patient_id)
        if patient is None:
            raise ValueError("Patient not found.")
        answers = patient["answers"]
        next_q = self.get_next_question(answers)
        progress = self.get_progress(answers)
        return {
            "completed": next_q is None,
            "next_question": next_q,
            "progress": progress,
        }


# Per-patient engine cache (mirrors `engines[patient_id] = AssessmentEngine(...)`
# rather than a single shared global engine instance).
_engines: Dict[str, AssessmentEngine] = {}
_engines_lock = threading.Lock()


def get_engine(patient_id: str) -> AssessmentEngine:
    with _engines_lock:
        if patient_id not in _engines:
            _engines[patient_id] = AssessmentEngine(patient_id)
        return _engines[patient_id]


def all_questions() -> List[Dict[str, Any]]:
    return _load_questions()
