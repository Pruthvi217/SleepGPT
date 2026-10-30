"""Pure token logic (no web framework) — see utils/auth.py for the FastAPI dependencies."""
from __future__ import annotations

import base64, hashlib, hmac, json, os, secrets, time
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KEY: Optional[bytes] = None


def _secret() -> bytes:
    """SLEEPGPT_SECRET_KEY from .env; otherwise a random key persisted in backend/data/.session_secret
    (so tokens survive uvicorn --reload but the key never lives in source control)."""
    global _KEY
    if _KEY is not None:
        return _KEY
    env = os.environ.get("SLEEPGPT_SECRET_KEY", "").strip()
    if env:
        _KEY = env.encode()
    else:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        p = _DATA_DIR / ".session_secret"
        if not p.exists():
            p.write_text(secrets.token_hex(32))
        _KEY = p.read_text().strip().encode()
    return _KEY


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(sub: str, role: str, ttl_seconds: Optional[int] = None) -> str:
    if ttl_seconds is None:
        ttl_seconds = int(float(os.environ.get("SLEEPGPT_TOKEN_TTL_HOURS", "12")) * 3600)
    body = _b64(json.dumps({"sub": sub, "role": role, "exp": int(time.time()) + ttl_seconds}).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> dict:
    """Returns the payload or raises ValueError."""
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(body))
    except Exception as exc:
        raise ValueError("invalid token") from exc
    if payload.get("exp", 0) < time.time():
        raise ValueError("token expired")
    if payload.get("role") not in ("patient", "admin"):
        raise ValueError("invalid role")
    return payload


