"""Loads the persisted Chroma vector store (built by rag/ingest.py) and
exposes a simple `retrieve(query, k)` function. Returns an empty list
gracefully if the knowledge base hasn't been ingested yet — callers must
not assume retrieval succeeds.

IMPORTANT: readiness is re-checked (cheaply, via Chroma's collection
count) on every call rather than cached permanently. This means running
`rag/ingest.py` while the backend is already up will be picked up on
the very next request — no backend restart required. Only the (more
expensive) sentence-transformers embedder model is loaded once and
cached — it is NOT reloaded on every call.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_VECTOR_DB_DIR = os.path.join(_ROOT, "vector_db")
_COLLECTION_NAME = "sleepgpt_knowledge_base"

_state = {"embedder": None}
_lock = threading.Lock()


def _check_collection() -> Tuple[bool, Optional[Any]]:
    """Cheap, always-fresh check of whether the vector store has data.
    Returns (ready, collection_or_None)."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=_VECTOR_DB_DIR)
        collection = client.get_or_create_collection(_COLLECTION_NAME)
        return collection.count() > 0, collection
    except Exception:
        return False, None


def is_ready() -> bool:
    ready, _ = _check_collection()
    return ready


def _get_embedder():
    """Loaded once and cached — never reloaded per-request."""
    with _lock:
        if _state["embedder"] is None:
            from sentence_transformers import SentenceTransformer

            _state["embedder"] = SentenceTransformer("all-MiniLM-L6-v2")
        return _state["embedder"]


def retrieve(query: str, k: int = 6, max_chars_per_chunk: int = 800) -> List[Dict[str, Any]]:
    """Returns [{"text": ..., "source": ..., "filename": ...}, ...] or [].

    `k` deliberately over-fetches (6) relative to the 3 chunks actually
    used downstream (see dedupe_chunks) — this gives dedup room to drop
    duplicates/near-duplicates without starving the final context.
    `max_chars_per_chunk` truncates each chunk (700-900 char target).
    """
    ready, collection = _check_collection()
    if not ready:
        return []
    try:
        embedder = _get_embedder()
        query_embedding = embedder.encode([query]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=k)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [
            {
                "text": (doc or "")[:max_chars_per_chunk],
                "source": meta.get("source"),
                "filename": meta.get("filename"),
            }
            for doc, meta in zip(docs, metas)
        ]
    except Exception:
        return []


def dedupe_chunks(chunks: List[Dict[str, Any]], max_chunks: int = 3) -> List[Dict[str, Any]]:
    """Removes exact/near-duplicate chunks (same normalized text, or the
    same source document appearing repeatedly) and caps the result at
    `max_chunks` (default 3 — the "best 3 chunks" the spec asks for),
    preferring source diversity. Chroma's nearest-neighbor search
    commonly returns several overlapping/adjacent chunks from the same
    PDF, which wastes context budget without adding new evidence.
    """
    seen_text = set()
    deduped: List[Dict[str, Any]] = []

    for chunk in chunks:
        normalized_text = " ".join((chunk.get("text") or "").split()).lower()[:200]
        doc_key = (chunk.get("source"), chunk.get("filename"))
        if not normalized_text or normalized_text in seen_text:
            continue
        # At most 1 chunk per document by default (max_chunks=3 across
        # 3 different documents gives the broadest evidence coverage);
        # relax to 2 only if we're short on distinct documents overall.
        doc_count = sum(1 for d in deduped if (d.get("source"), d.get("filename")) == doc_key)
        max_per_doc = 1 if len({(c.get("source"), c.get("filename")) for c in chunks}) >= max_chunks else 2
        if doc_count >= max_per_doc:
            continue
        seen_text.add(normalized_text)
        deduped.append(chunk)
        if len(deduped) >= max_chunks:
            break

    return deduped
