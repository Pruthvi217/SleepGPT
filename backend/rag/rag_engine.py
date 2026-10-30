"""
SleepGPT — RAG Analysis Engine
---------------------------------
Produces the AI summary as 8 sections:
    1. Overall interpretation
    2. Main risk factors
    3. Questionnaire concerns
    4. Possible causes / contributing factors
    5. Preventive / risk-reduction measures
    6. Recommended next step
    7. Patient summary (personalized synthesis — NOT a repeat of #1)
    8. Patient-friendly explanation

STRICT SEPARATION OF CONCERNS: questionnaire scores (BMI, STOP-BANG,
Berlin, NoSAS, ESS, overall risk) are calculated ONLY by
backend/services/scoring.py. This module receives those numbers as
already-final and NEVER asks the LLM to compute or alter them.

WHY GENERATION WAS TIMING OUT (and what changed here):
Generation time on a local CPU-bound 8B model scales almost entirely
with *output* token count, not prompt size — a 1-word test reply
finishes almost instantly while an ~450-500 token structured summary
genuinely takes tens of seconds. On top of that, Ollama's default
num_ctx can allocate a larger context window than needed, slowing every
request regardless of actual prompt length. The fix here is not a
bigger timeout: it's fewer, better chunks (best 3, deduped), a smaller
context budget (~2500-3000 chars), an explicit num_ctx=4096, a lower
temperature (0.2) for more deterministic/shorter output, and a timeout
(150s) that's a genuine safety margin for the generation length being
requested rather than an arbitrary small number.

FAILURE STATE: if Ollama genuinely fails/times out even with all of the
above, the fallback is still GROUNDED in whatever was retrieved (real
cited excerpts from the knowledge base), not generic boilerplate — and
is labeled honestly: generation_method="rule_based_fallback",
knowledge_base_used reflects whether retrieval actually found evidence,
llm_used=False. Success is generation_method="rag_llm",
knowledge_base_used=True, llm_used=True.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from llm import ollama_client
from rag import retriever

MAX_CONTEXT_CHARS = 2800
MAX_CHUNKS = 3
NUM_PREDICT = 300
TEMPERATURE = 0.2
NUM_CTX = 4096
GENERATION_TIMEOUT = 180.0
KEEP_ALIVE = "30m"

_SYSTEM_PROMPT = (
    "You are SleepGPT, a clinical decision-support assistant for sleep apnea "
    "screening.\n\n"
    "You are NOT a diagnostic system.\n\n"
    "Use the patient's screening results to personalize the response.\n\n"
    "Use the supplied knowledge-base evidence as the source for medical "
    "explanations, risk factors, symptoms, causes, prevention and follow-up. "
    "Do not invent medical facts that are not supported by the supplied "
    "evidence. If the evidence does not support a section, write: "
    "'Insufficient supporting information was retrieved from the SleepGPT "
    "knowledge base for this point.'\n\n"
    "Do not claim that the patient definitely has sleep apnea. This is a "
    "screening result, not a diagnosis.\n\n"
    "Keep the response concise and patient-friendly. Each section must be "
    "1-2 short sentences (about 25-35 words) — do not write long paragraphs."
)

_SECTION_LABELS = {
    "OVERALL INTERPRETATION": "overall_interpretation",
    "MAIN RISK FACTORS": "main_risk_factors",
    "QUESTIONNAIRE CONCERNS": "questionnaire_concerns",
    "POSSIBLE CAUSES OR CONTRIBUTING FACTORS": "possible_contributing_factors",
    "PREVENTIVE / RISK-REDUCTION MEASURES": "preventive_measures",
    "RECOMMENDED NEXT STEP": "recommended_next_step",
    "PATIENT SUMMARY": "patient_summary",
    "PATIENT-FRIENDLY EXPLANATION": "patient_friendly_explanation",
}
_LABEL_ITEMS = sorted(_SECTION_LABELS.items(), key=lambda kv: -len(kv[0]))
_ALL_FIELDS = list(_SECTION_LABELS.values())

_INSUFFICIENT_EVIDENCE_NOTE = (
    "Insufficient supporting information was retrieved from the SleepGPT "
    "knowledge base for this point."
)


# ---------------------------------------------------------------------
# Patient profile / query building
# ---------------------------------------------------------------------

def _describe_risk_factors(scores: Dict[str, Any]) -> List[str]:
    """Human-readable risk-factor phrases derived from the ALREADY
    CALCULATED stopbang criteria — used to build the query/profile and
    the rule-based fallback, never sent back as if the LLM computed
    them."""
    criteria = scores.get("stopbang", {}).get("criteria", {})
    phrases = []
    if criteria.get("S_snoring"):
        phrases.append("snoring")
    if criteria.get("T_tiredness"):
        phrases.append("daytime tiredness")
    if criteria.get("O_observed_apnea"):
        phrases.append("witnessed apnea")
    if criteria.get("P_pressure_hypertension"):
        phrases.append("hypertension")
    if criteria.get("B_bmi_over_35"):
        phrases.append("elevated BMI")
    if criteria.get("A_age_over_50"):
        phrases.append("age over 50")
    if criteria.get("N_neck_over_40cm"):
        phrases.append("increased neck circumference")
    if criteria.get("G_male_gender"):
        phrases.append("male sex")
    return phrases


def _build_patient_profile(scores: Dict[str, Any]) -> str:
    """Short, structured screening profile block — used both to build
    the retrieval query and embedded directly in the LLM prompt."""
    risk_factors = _describe_risk_factors(scores)
    symptoms_line = ", ".join(risk_factors) if risk_factors else "none flagged"
    return (
        "Patient screening profile:\n"
        f"STOP-BANG: {scores['stopbang']['score']}/8 ({scores['stopbang']['risk']})\n"
        f"Berlin: {scores['berlin']['positive_categories']}/3 positive categories ({scores['berlin']['risk']})\n"
        f"NoSAS: {scores['nosas']['score']}/17 ({scores['nosas']['risk']})\n"
        f"ESS: {scores['ess']['score']}/24 ({scores['ess']['interpretation']})\n"
        f"Overall risk: {scores['overall_risk']}\n\n"
        f"Relevant symptoms: {symptoms_line}"
    )


def _build_query(scores: Dict[str, Any]) -> str:
    """Concise retrieval query — the profile plus fixed topic keywords."""
    profile = _build_patient_profile(scores)
    return (
        f"{profile}\n\n"
        "Retrieve evidence relevant to: interpretation of these scores, risk "
        "factors, symptoms, possible contributing factors, consequences, "
        "prevention/risk reduction, recommended diagnostic follow-up."
    )


# ---------------------------------------------------------------------
# Context selection — the actual timeout fix
# ---------------------------------------------------------------------

def _select_context(chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
    """Dedupes and caps chunks to the best MAX_CHUNKS, fit within
    MAX_CONTEXT_CHARS total. Small, high-quality context = fast, focused
    generation."""
    deduped = retriever.dedupe_chunks(chunks, max_chunks=MAX_CHUNKS)

    selected: List[Dict[str, Any]] = []
    running_total = 0
    for chunk in deduped:
        text = chunk["text"]
        remaining_budget = MAX_CONTEXT_CHARS - running_total
        if remaining_budget <= 0:
            break
        if len(text) > remaining_budget:
            text = text[:remaining_budget]
        selected.append({**chunk, "text": text})
        running_total += len(text)

    context_text = "\n\n".join(f"[{c['source']}/{c['filename']}] {c['text']}" for c in selected)
    return selected, context_text


# ---------------------------------------------------------------------
# Rule-based / knowledge-base-grounded fallback
# ---------------------------------------------------------------------

def _first_sentences(text: str, max_chars: int = 220) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    return (truncated[: last_period + 1] if last_period > 40 else truncated).strip()


def _pick_chunk(chunks: List[Dict[str, Any]], keywords: List[str], exclude_idx: set) -> int:
    for i, c in enumerate(chunks):
        if i in exclude_idx:
            continue
        if any(kw in c["text"].lower() for kw in keywords):
            return i
    return -1


def _rule_based_fallback(scores: Dict[str, Any], chunks: List[Dict[str, Any]],
                          knowledge_base_used: bool) -> Dict[str, Any]:
    """Ollama failed/unavailable/timed out. If retrieval succeeded
    (chunks is non-empty), Risk Factors/Concerns/Next Step/Patient
    Summary are still populated from the ACTUAL calculated scores
    (never blank), and Possible Causes/Preventive Measures pull real
    cited excerpts from the retrieved chunks where a relevant one
    exists — never silently disguised as LLM output."""
    overall = scores["overall_risk"]
    risk_factors = _describe_risk_factors(scores)
    risk_factors_text = (
        (", ".join(risk_factors).capitalize() + ".")
        if risk_factors
        else "No major risk factors were identified from the screening criteria."
    )

    stopbang, berlin, nosas, ess = scores["stopbang"], scores["berlin"], scores["nosas"], scores["ess"]
    concerns = []
    if ess.get("score") is not None and ess["score"] > 10:
        concerns.append(f"elevated Epworth Sleepiness Scale score ({ess['score']}/24)")
    if berlin["positive_categories"] >= 2:
        concerns.append("Berlin Questionnaire positive in 2 or more categories")
    if stopbang["score"] >= 3:
        concerns.append(f"STOP-BANG score of {stopbang['score']}/8")
    if nosas["score"] >= 8:
        concerns.append(f"elevated NoSAS score ({nosas['score']}/17)")
    concerns_text = (", ".join(concerns).capitalize() + ".") if concerns else "No significant concerns flagged across the screening instruments."

    if overall == "High risk":
        next_step = (
            "Consult a sleep medicine physician promptly to discuss these results "
            "and consider a formal sleep study (polysomnography or a home sleep "
            "apnea test)."
        )
    elif overall == "Intermediate risk":
        next_step = (
            "Discuss these screening results with a primary care physician, who "
            "may refer you to a sleep specialist for further evaluation."
        )
    else:
        next_step = (
            "Current screening does not suggest high risk. Continue healthy sleep "
            "habits and mention any new symptoms to your doctor."
        )

    used_idx: set = set()
    causes_idx = _pick_chunk(
        chunks, ["cause", "risk factor", "obesity", "airway", "contribut", "associated with"], used_idx
    )
    if causes_idx == -1 and chunks:
        causes_idx = 0
    if causes_idx != -1:
        used_idx.add(causes_idx)
        c = chunks[causes_idx]
        possible_contributing_factors = (
            f"From the SleepGPT knowledge base ({c['source']}/{c['filename']}): "
            f"{_first_sentences(c['text'])}"
        )
    else:
        possible_contributing_factors = _INSUFFICIENT_EVIDENCE_NOTE

    prevention_idx = _pick_chunk(
        chunks, ["prevent", "weight loss", "lifestyle", "reduce", "treatment", "cpap", "avoid"], used_idx
    )
    if prevention_idx != -1:
        used_idx.add(prevention_idx)
        c = chunks[prevention_idx]
        preventive_measures = (
            f"From the SleepGPT knowledge base ({c['source']}/{c['filename']}): "
            f"{_first_sentences(c['text'])}"
        )
    else:
        preventive_measures = _INSUFFICIENT_EVIDENCE_NOTE

    overall_interpretation = (
        f"Based on the combined results of the STOP-BANG, Berlin, NoSAS, and Epworth "
        f"Sleepiness Scale questionnaires, this screening indicates an overall "
        f"'{overall}' for obstructive sleep apnea. This is a screening result "
        f"generated from validated questionnaires, not a clinical diagnosis."
    )

    patient_summary = (
        f"This patient's screening indicates {overall.lower()} for obstructive sleep "
        f"apnea. {('Risk factors identified: ' + risk_factors_text) if risk_factors else ''} "
        f"{concerns_text} {next_step} These questionnaire results are a screening "
        f"tool, not a diagnosis."
    ).strip()

    patient_friendly_explanation = (
        f"Your answers suggest a {overall.lower()} level of concern for sleep apnea "
        f"based on standard screening questionnaires. This does not mean you "
        f"definitely have sleep apnea — only a sleep specialist can diagnose it, "
        f"usually with an overnight sleep study. {next_step}"
    )

    sources = sorted({f"{c['source']}/{c['filename']}" for c in chunks})

    return {
        "overall_interpretation": overall_interpretation,
        "main_risk_factors": risk_factors_text,
        "questionnaire_concerns": concerns_text,
        "possible_contributing_factors": possible_contributing_factors,
        "preventive_measures": preventive_measures,
        "recommended_next_step": next_step,
        "patient_summary": patient_summary,
        "patient_friendly_explanation": patient_friendly_explanation,
        "generation_method": "rule_based_fallback",
        "knowledge_base_used": knowledge_base_used,
        "llm_used": False,
        "sources": sources,
    }


# ---------------------------------------------------------------------
# LLM output parsing (robust to markdown, missing colons, etc.)
# ---------------------------------------------------------------------

def _strip_markdown(line: str) -> str:
    return re.sub(r"\*+", "", line).strip()


def _parse_llm_sections(raw: str) -> Dict[str, str]:
    sections: Dict[str, str] = {v: "" for v in _ALL_FIELDS}
    current_key = None

    for raw_line in raw.splitlines():
        cleaned = _strip_markdown(raw_line)
        upper = cleaned.upper()
        matched_key = None
        remainder = ""

        for label, key in _LABEL_ITEMS:
            if upper == label or upper == f"{label}:":
                matched_key = key
                remainder = ""
                break
            if upper.startswith(f"{label}:"):
                matched_key = key
                remainder = cleaned[len(label) + 1:].strip()
                break

        if matched_key:
            current_key = matched_key
            sections[current_key] = remainder
        elif current_key:
            if cleaned:
                sections[current_key] = (sections[current_key] + " " + cleaned).strip()

    return {k: (v.strip() or _INSUFFICIENT_EVIDENCE_NOTE) for k, v in sections.items()}


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

def generate_assessment_summary(scores: Dict[str, Any]) -> Dict[str, Any]:
    """Exactly ONE Ollama generation call per invocation."""
    kb_ready = retriever.is_ready()
    print(f"Knowledge base ready: {kb_ready}")

    if not kb_ready:
        return _rule_based_fallback(scores, [], knowledge_base_used=False)

    query = _build_query(scores)
    raw_chunks = retriever.retrieve(query, k=6, max_chars_per_chunk=800)
    print(f"Retrieved chunks: {len(raw_chunks)}")

    selected_chunks, context_text = _select_context(raw_chunks)
    print(f"Unique chunks: {len(selected_chunks)}")
    print(f"Context characters: {len(context_text)}")

    if not selected_chunks:
        return _rule_based_fallback(scores, [], knowledge_base_used=False)

    llm_ready = ollama_client.is_available()
    print(f"Ollama available: {llm_ready}")
    print(f"Ollama model: {ollama_client.OLLAMA_MODEL}")

    if not llm_ready:
        return _rule_based_fallback(scores, selected_chunks, knowledge_base_used=True)

    profile = _build_patient_profile(scores)
    prompt = (
        f"{profile}\n\n"
        f"KNOWLEDGE BASE EVIDENCE:\n{context_text}\n\n"
        "Respond with exactly these sections, each on its own line as a label "
        "followed by 1-2 short sentences (about 25-35 words each) — be concise, "
        "not exhaustive:\n\n"
        "OVERALL INTERPRETATION:\n"
        "MAIN RISK FACTORS:\n"
        "QUESTIONNAIRE CONCERNS:\n"
        "POSSIBLE CAUSES OR CONTRIBUTING FACTORS:\n"
        "PREVENTIVE / RISK-REDUCTION MEASURES:\n"
        "RECOMMENDED NEXT STEP:\n"
        "PATIENT SUMMARY:\n"
        "PATIENT-FRIENDLY EXPLANATION:\n"
    )
    print(f"Prompt characters: {len(prompt)}")
    print("Generating summary...")

    raw = ollama_client.generate(
        prompt,
        system=_SYSTEM_PROMPT,
        timeout=GENERATION_TIMEOUT,
        num_predict=NUM_PREDICT,
        temperature=TEMPERATURE,
        num_ctx=NUM_CTX,
        keep_alive=KEEP_ALIVE,
    )

    if not raw:
        print("Generation failed or returned empty response.")
        return _rule_based_fallback(scores, selected_chunks, knowledge_base_used=True)

    parsed = _parse_llm_sections(raw)
    parsed["generation_method"] = "rag_llm"
    parsed["knowledge_base_used"] = True
    parsed["llm_used"] = True
    parsed["sources"] = sorted({f"{c['source']}/{c['filename']}" for c in selected_chunks})
    return parsed
