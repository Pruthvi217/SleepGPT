"""
SleepGPT — Knowledge Base Ingestion Pipeline
-----------------------------------------------
Scans `knowledge_base/<SOURCE>/*.pdf|*.txt|*.docx`, extracts text, chunks
it, embeds it with sentence-transformers, and persists a Chroma vector
store at `vector_db/`.

WHERE TO PUT YOUR DOCUMENTS:
    knowledge_base/AASM/        - AASM clinical guidelines
    knowledge_base/STOP_BANG/   - STOP-BANG questionnaire references
    knowledge_base/Berlin/      - Berlin Questionnaire references
    knowledge_base/ESS/         - Epworth Sleepiness Scale references
    knowledge_base/NoSAS/       - NoSAS score references
    knowledge_base/IEEE/        - IEEE research papers
    knowledge_base/Elsevier/    - Elsevier research papers
    knowledge_base/Springer/    - Springer research papers
    knowledge_base/MDPI/        - MDPI research papers
    knowledge_base/PLOS/        - PLOS research papers

Accepted formats: .pdf, .txt, .md, .docx

HOW TO RUN (after adding documents):
    cd backend
    python -m rag.ingest

This is idempotent — re-running rebuilds the vector store from whatever
is currently in knowledge_base/. No documents are required to run the
rest of the application; rag_engine.py falls back to a rule-based summary
until this has been run at least once.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KNOWLEDGE_BASE_DIR = os.path.join(_ROOT, "knowledge_base")
_VECTOR_DB_DIR = os.path.join(_ROOT, "vector_db")
_COLLECTION_NAME = "sleepgpt_knowledge_base"

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


def _extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            import docx
            doc = docx.Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        else:  # .txt / .md
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as exc:  # noqa: BLE001 - log and skip bad files
        print(f"  [WARN] Failed to extract {filepath}: {exc}")
        return ""


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def discover_documents() -> list[tuple[str, str]]:
    """Returns list of (source_folder, absolute_filepath)."""
    found = []
    if not os.path.isdir(_KNOWLEDGE_BASE_DIR):
        return found
    for source in sorted(os.listdir(_KNOWLEDGE_BASE_DIR)):
        source_dir = os.path.join(_KNOWLEDGE_BASE_DIR, source)
        if not os.path.isdir(source_dir):
            continue
        for fname in sorted(os.listdir(source_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in _SUPPORTED_EXTENSIONS:
                found.append((source, os.path.join(source_dir, fname)))
    return found


def run_ingestion() -> dict:
    documents = discover_documents()
    if not documents:
        print("No documents found in knowledge_base/. Nothing to ingest.")
        print("Add PDFs/text/docx files to the folders listed in this file's docstring, then re-run.")
        return {"status": "empty", "documents_found": 0, "chunks_indexed": 0}

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        print(f"[ERROR] Missing dependency: {exc}. Install backend/requirements.txt first.")
        return {"status": "error", "error": str(exc)}

    print(f"Found {len(documents)} document(s). Extracting + chunking...")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=_VECTOR_DB_DIR)
    collection = client.get_or_create_collection(_COLLECTION_NAME)

    all_ids, all_texts, all_metadatas = [], [], []
    for source, filepath in documents:
        text = _extract_text(filepath)
        chunks = _chunk_text(text)
        fname = os.path.basename(filepath)
        for i, chunk in enumerate(chunks):
            all_ids.append(f"{source}::{fname}::{i}")
            all_texts.append(chunk)
            all_metadatas.append({"source": source, "filename": fname})

    if not all_texts:
        print("Documents were found but no extractable text was produced.")
        return {"status": "empty", "documents_found": len(documents), "chunks_indexed": 0}

    print(f"Embedding {len(all_texts)} chunk(s)...")
    embeddings = embedder.encode(all_texts, show_progress_bar=True).tolist()

    # Reset collection contents before re-adding (idempotent rebuild)
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(_COLLECTION_NAME)
    collection.add(ids=all_ids, documents=all_texts, embeddings=embeddings, metadatas=all_metadatas)

    print(f"Done. Indexed {len(all_texts)} chunks into {_VECTOR_DB_DIR}")
    return {"status": "ok", "documents_found": len(documents), "chunks_indexed": len(all_texts)}


if __name__ == "__main__":
    sys.exit(0 if run_ingestion().get("status") in ("ok", "empty") else 1)
