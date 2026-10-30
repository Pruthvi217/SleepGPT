"""Thin client for a local Ollama LLM. Fails gracefully if Ollama is not
running / not installed — callers must handle `None` return values and
fall back to a rule-based response.

Default model is llama3.1:8b. Override via OLLAMA_MODEL if different.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def is_available() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def generate(
    prompt: str,
    system: Optional[str] = None,
    timeout: float = 180.0,
    num_predict: int = 300,
    temperature: float = 0.2,
    num_ctx: int = 4096,
    keep_alive: str = "30m",
) -> Optional[str]:
    """Returns generated text, or None if Ollama is unavailable / errors.

    A single request per call. Defaults are tuned for reliable local
    generation given this project's measured throughput (~4-5 tok/s on
    CPU for llama3.1:8b — NOT the ~39 tok/s a short, early-stopping test
    prompt might suggest):
      - num_predict: 300 (not 450+) — output length is the dominant
        cost. At ~4-5 tok/s, 450 tokens alone can take 90-110s; 300
        keeps pure generation time in the ~60-75s range with margin.
      - keep_alive: "30m" — Ollama's default unloads an idle model after
        ~5 minutes. A 35-question assessment easily takes longer than
        that, so without this, the generation call can pay for a full
        4.9GB model reload from disk before generation even starts.
        Setting this keeps the model resident so THIS call and the next
        one both stay fast.
      - num_ctx: bounds context window (avoids Ollama over-allocating).
      - temperature: lowered for more deterministic, less meandering
        (and often shorter) output.
      - timeout: a genuine safety margin — covers a worst-case cold
        model load (if keep_alive didn't help, e.g. first request ever)
        plus real generation time at measured throughput.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
            "num_ctx": num_ctx,
        },
    }
    if system:
        payload["system"] = system

    start = time.time()
    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=timeout)
        print(f"Ollama HTTP status: {resp.status_code}")
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        elapsed = round(time.time() - start, 1)
        if not text:
            print(f"Ollama returned an empty response after {elapsed}s.")
            return None
        print(f"Generated characters: {len(text)}")
        print(f"Ollama generation successful. ({elapsed}s)")
        return text
    except requests.Timeout:
        print(f"Ollama generation TIMEOUT after {timeout} seconds.")
        return None
    except requests.RequestException as exc:
        print(f"Ollama generation failed: {type(exc).__name__}: {exc}")
        return None
