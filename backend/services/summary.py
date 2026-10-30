"""Builds the patient-facing summary object saved against the patient
record (see spec section 17)."""

from __future__ import annotations

from typing import Any, Dict


def build_patient_summary(patient_id: str, scores: Dict[str, Any], rag_analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_id": patient_id,
        "overall_risk": scores["overall_risk"],
        "bmi": scores["bmi"],
        "stop_bang": {"score": scores["stopbang"]["score"], "risk": scores["stopbang"]["risk"]},
        "berlin": {"positive_categories": scores["berlin"]["positive_categories"], "risk": scores["berlin"]["risk"]},
        "nosas": {"score": scores["nosas"]["score"], "risk": scores["nosas"]["risk"]},
        "ess": {"score": scores["ess"]["score"], "risk": scores["ess"]["risk"]},
        "main_risk_factors": rag_analysis.get("main_risk_factors", ""),
        "recommended_next_step": rag_analysis.get("recommended_next_step", ""),
        "ai_summary": rag_analysis.get("patient_summary") or rag_analysis.get("overall_interpretation", ""),
        "possible_contributing_factors": rag_analysis.get("possible_contributing_factors", ""),
        "preventive_measures": rag_analysis.get("preventive_measures", ""),
        "disclaimer": scores["disclaimer"],
    }
