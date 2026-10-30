"""
SleepGPT — Screening Score Calculators
----------------------------------------
Pure functions that turn a patient's `answers` dict (keyed by question id,
as strings, matching datasets/questions.json) into the standard validated
screening scores.

IMPORTANT: These are SCREENING tools, not diagnostic tests. Callers must
always surface the accompanying "not a diagnosis" disclaimer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Question-id map (must stay in sync with datasets/questions.json)
Q_AGE = "1"
Q_SEX = "2"
Q_HEIGHT_CM = "3"
Q_WEIGHT_KG = "4"
Q_NECK_CM = "5"
Q_LOUD_SNORING = "9"
Q_SNORING_LOUDNESS = "10"
Q_SNORING_FREQUENCY = "11"
Q_SNORING_BOTHERS_OTHERS = "12"
Q_OBSERVED_APNEA = "13"
Q_OBSERVED_APNEA_FREQUENCY = "14"
Q_DAYTIME_TIREDNESS = "15"
Q_TIREDNESS_FREQUENCY = "16"
Q_FALLEN_ASLEEP_DRIVING = "17"
Q_HYPERTENSION = "18"

ESS_QUESTION_IDS = [str(i) for i in range(20, 28)]  # 20..27


def _is_yes(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "yes"


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_bmi(answers: Dict[str, Any]) -> Optional[float]:
    height_cm = _to_float(answers.get(Q_HEIGHT_CM))
    weight_kg = _to_float(answers.get(Q_WEIGHT_KG))
    if not height_cm or not weight_kg or height_cm <= 0:
        return None
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m ** 2), 1)


def compute_stopbang(answers: Dict[str, Any], bmi: Optional[float]) -> Dict[str, Any]:
    age = _to_float(answers.get(Q_AGE))
    sex = answers.get(Q_SEX)
    neck_cm = _to_float(answers.get(Q_NECK_CM))

    criteria = {
        "S_snoring": _is_yes(answers.get(Q_LOUD_SNORING)),
        "T_tiredness": _is_yes(answers.get(Q_DAYTIME_TIREDNESS)),
        "O_observed_apnea": _is_yes(answers.get(Q_OBSERVED_APNEA)),
        "P_pressure_hypertension": _is_yes(answers.get(Q_HYPERTENSION)),
        "B_bmi_over_35": bool(bmi and bmi > 35),
        "A_age_over_50": bool(age and age > 50),
        "N_neck_over_40cm": bool(neck_cm and neck_cm > 40),
        "G_male_gender": sex == "Male",
    }
    score = sum(1 for v in criteria.values() if v)

    if score >= 5:
        risk = "High risk"
    elif score >= 3:
        risk = "Intermediate risk"
    else:
        risk = "Low risk"

    return {
        "score": score,
        "maximum_score": 8,
        "criteria": criteria,
        "risk": risk,
    }


def compute_berlin(answers: Dict[str, Any], bmi: Optional[float]) -> Dict[str, Any]:
    # Category 1: snoring behavior
    cat1_points = 0
    if _is_yes(answers.get(Q_LOUD_SNORING)):
        loudness = answers.get(Q_SNORING_LOUDNESS)
        frequency = answers.get(Q_SNORING_FREQUENCY)
        bothers = _is_yes(answers.get(Q_SNORING_BOTHERS_OTHERS))
        if loudness in ("Louder than talking", "Very loud - can be heard in the next room"):
            cat1_points += 1
        if frequency in ("3-4 nights per week", "Almost every night"):
            cat1_points += 1
        if bothers:
            cat1_points += 1
    if _is_yes(answers.get(Q_OBSERVED_APNEA)):
        apnea_freq = answers.get(Q_OBSERVED_APNEA_FREQUENCY)
        if apnea_freq in ("Nearly every day", "3-4 times a week"):
            cat1_points += 2
        elif apnea_freq in ("1-2 times a week", "1-2 times a month"):
            cat1_points += 1
    category1_positive = cat1_points >= 2

    # Category 2: daytime sleepiness / fatigue
    cat2_points = 0
    if _is_yes(answers.get(Q_DAYTIME_TIREDNESS)):
        tiredness_freq = answers.get(Q_TIREDNESS_FREQUENCY)
        if tiredness_freq in ("Nearly every day", "3-4 times a week"):
            cat2_points += 2
        elif tiredness_freq == "1-2 times a week":
            cat2_points += 1
    if _is_yes(answers.get(Q_FALLEN_ASLEEP_DRIVING)):
        cat2_points += 1
    category2_positive = cat2_points >= 2

    # Category 3: obesity or hypertension
    category3_positive = bool(bmi and bmi > 30) or _is_yes(answers.get(Q_HYPERTENSION))

    positive_categories = sum([category1_positive, category2_positive, category3_positive])

    risk = "High risk" if positive_categories >= 2 else "Low risk"

    return {
        "positive_categories": positive_categories,
        "maximum_categories": 3,
        "category_breakdown": {
            "category_1_snoring": category1_positive,
            "category_2_sleepiness": category2_positive,
            "category_3_obesity_hypertension": category3_positive,
        },
        "risk": risk,
    }


def compute_nosas(answers: Dict[str, Any], bmi: Optional[float]) -> Dict[str, Any]:
    age = _to_float(answers.get(Q_AGE))
    sex = answers.get(Q_SEX)
    neck_cm = _to_float(answers.get(Q_NECK_CM))

    score = 0
    if neck_cm:
        if neck_cm >= 44:
            score += 4
        elif neck_cm >= 40:
            score += 3
    if bmi:
        if bmi >= 30:
            score += 5
        elif bmi >= 25:
            score += 3
    if _is_yes(answers.get(Q_LOUD_SNORING)):
        score += 2
    if age and age > 55:
        score += 4
    if sex == "Male":
        score += 2

    risk = "High risk" if score >= 8 else "Low risk"

    return {
        "score": score,
        "maximum_score": 17,
        "risk": risk,
    }


def compute_ess(answers: Dict[str, Any]) -> Dict[str, Any]:
    total = 0
    answered_count = 0
    for qid in ESS_QUESTION_IDS:
        raw = answers.get(qid)
        value = _to_float(raw)
        if value is None and isinstance(raw, str) and raw and raw[0].isdigit():
            value = _to_float(raw[0])
        if value is not None:
            total += int(value)
            answered_count += 1

    if answered_count == 0:
        return {"score": None, "maximum_score": 24, "interpretation": "Not assessed", "risk": "Not assessed"}

    if total <= 10:
        interpretation = "Normal daytime sleepiness"
        risk = "Low risk"
    elif total <= 15:
        interpretation = "Moderate excessive daytime sleepiness"
        risk = "Intermediate risk"
    else:
        interpretation = "Severe excessive daytime sleepiness"
        risk = "High risk"

    return {
        "score": total,
        "maximum_score": 24,
        "interpretation": interpretation,
        "risk": risk,
    }


_RISK_RANK = {"Low risk": 0, "Intermediate risk": 1, "High risk": 2, "Not assessed": 0}


def compute_overall_risk(stopbang: Dict[str, Any], berlin: Dict[str, Any],
                          nosas: Dict[str, Any], ess: Dict[str, Any]) -> str:
    ranks = [
        _RISK_RANK.get(stopbang.get("risk"), 0),
        _RISK_RANK.get(berlin.get("risk"), 0),
        _RISK_RANK.get(nosas.get("risk"), 0),
        _RISK_RANK.get(ess.get("risk"), 0),
    ]
    max_rank = max(ranks)
    high_count = ranks.count(2)
    if max_rank == 2 and high_count >= 2:
        return "High risk"
    if max_rank == 2 or ranks.count(1) >= 2:
        return "Intermediate risk"
    return "Low risk"


def compute_all_scores(answers: Dict[str, Any]) -> Dict[str, Any]:
    bmi = compute_bmi(answers)
    stopbang = compute_stopbang(answers, bmi)
    berlin = compute_berlin(answers, bmi)
    nosas = compute_nosas(answers, bmi)
    ess = compute_ess(answers)
    overall_risk = compute_overall_risk(stopbang, berlin, nosas, ess)

    return {
        "bmi": bmi,
        "stopbang": stopbang,
        "berlin": berlin,
        "nosas": nosas,
        "ess": ess,
        "overall_risk": overall_risk,
        "disclaimer": (
            "This is a screening result generated from validated questionnaires. "
            "It is NOT a medical diagnosis. Please consult a qualified sleep "
            "physician for clinical evaluation, and polysomnography (PSG) for "
            "definitive diagnosis of sleep apnea."
        ),
    }
