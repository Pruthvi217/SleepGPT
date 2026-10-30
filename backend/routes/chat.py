"""General-purpose chat endpoint, grounded in the RAG knowledge base when
available. Not tied to a specific patient's screening results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from llm import ollama_client
from ml import service as ml_service
from utils.auth import check_patient_access, get_session
from rag import retriever

router = APIRouter()

_SYSTEM_PROMPT = (
    "You are SleepGPT, an assistant for general sleep-health and sleep-apnea "
    "education. You are NOT a diagnostic tool. Never tell someone they "
    "definitely have or don't have sleep apnea. Encourage consulting a sleep "
    "physician for diagnosis. Keep answers concise and clear. When a 'Patient ML analysis' block is "
    "provided, explain ONLY those values in plain language; never calculate, change or invent AHI, "
    "SpO2 or any sensor value. State that the estimate is unvalidated and not a diagnosis."
)

_ML_KEYWORDS = ("ahi", "apnea-hypopnea", "apnoea", "spo2", "oxygen", "saturation", "sleep analysis",
                "ml ", "machine learning", "my result", "my analysis", "events", "sensor", "estimated")


class ChatRequest(BaseModel):
    message: str
    patient_id: str | None = None


@router.post("")
async def chat(payload: ChatRequest, session: dict = Depends(get_session)):
    message = payload.message.strip()
    if not message:
        return {"response": "Please enter a question.", "sources": []}

    # Patient-scoped context requires the session to own that SGP-XXXXXX id (or be admin).
    ml_block = None
    if payload.patient_id:
        check_patient_access(session, payload.patient_id)
        if any(k in message.lower() for k in _ML_KEYWORDS):
            ml_block = ml_service.chat_context(payload.patient_id)
            if ml_block is None:
                return {"response": "No ML sleep analysis is available for this patient yet, so I can't "
                                    "comment on an Estimated AHI or SpO2 results.", "sources": [], "llm_used": False}

    context_chunks = retriever.retrieve(message, k=4)
    llm_ready = ollama_client.is_available()

    if not llm_ready:
        if ml_block:
            return {"response": ml_service.deterministic_explanation(payload.patient_id), "sources": [], "llm_used": False}
        return {
            "response": (
                "The AI chat model is not currently available (Ollama is not "
                "running or reachable). Please try again later, or contact your "
                "administrator. This assistant cannot provide a diagnosis in any "
                "case — please consult a sleep physician for medical concerns."
            ),
            "sources": [],
            "llm_used": False,
        }

    context_text = "\n\n".join(c["text"] for c in context_chunks) if context_chunks else "No indexed reference documents yet."
    if ml_block:
        context_text = f"Patient ML analysis (authoritative, computed by the ML backend):\n{ml_block}\n\n{context_text}"
    prompt = f"Context:\n{context_text}\n\nQuestion: {message}\n\nAnswer:"
    response = ollama_client.generate(prompt, system=_SYSTEM_PROMPT)

    if not response:
        response = "Sorry, I couldn't generate a response right now. Please try again."

    return {
        "response": response,
        "sources": sorted({c["source"] for c in context_chunks}) if context_chunks else [],
        "llm_used": True,
    }
