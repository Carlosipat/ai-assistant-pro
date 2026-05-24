"""
services/document_service.py — Retrai v6
RAG (Retrieval-Augmented Generation) context builder.
Stores and retrieves project documents from Supabase or local files.
Used by chat.py to inject relevant document snippets into prompts.
"""
import os
import json
import time
import hashlib
from pathlib import Path
from typing import Optional
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
MEMORY_DIR   = Path(os.getenv("MEMORY_DIR", "/tmp/memory"))

MAX_CONTEXT_CHARS = 3000   # max chars of doc context to inject per query
MAX_DOCS_PER_PROJECT = 20  # max stored docs per project


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _use_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _docs_dir(user_id: str, project_id: str) -> Path:
    p = MEMORY_DIR / user_id / "projects" / project_id / "docs"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Simple keyword relevance scorer (no external deps) ───────────

def _relevance(query: str, text: str) -> float:
    """
    Basic TF-style relevance: fraction of query words found in text.
    Good enough for small doc sets without requiring a vector DB.
    """
    if not query or not text:
        return 0.0
    q_words = set(query.lower().split())
    t_lower = text.lower()
    hits = sum(1 for w in q_words if w in t_lower)
    return hits / max(len(q_words), 1)


# ── Local file helpers ────────────────────────────────────────────

def _local_list(user_id: str, project_id: str) -> list:
    d = _docs_dir(user_id, project_id)
    docs = []
    for f in d.glob("*.json"):
        try:
            with open(f) as fp:
                docs.append(json.load(fp))
        except Exception:
            pass
    return docs


def _local_save(user_id: str, project_id: str, doc: dict):
    p = _docs_dir(user_id, project_id) / f"{doc['id']}.json"
    with open(p, "w") as f:
        json.dump(doc, f, indent=2)


def _local_delete(user_id: str, project_id: str, doc_id: str):
    p = _docs_dir(user_id, project_id) / f"{doc_id}.json"
    if p.exists():
        p.unlink()


# ── Supabase helpers ──────────────────────────────────────────────

async def _sb_list_docs(user_id: str, project_id: str) -> list:
    url = (
        f"{SUPABASE_URL}/rest/v1/project_documents"
        f"?user_id=eq.{user_id}&project_id=eq.{project_id}"
        f"&select=id,filename,content,created_at"
        f"&order=created_at.desc"
    )
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=_sb_headers())
        r.raise_for_status()
        return r.json()


async def _sb_save_doc(doc: dict):
    url = f"{SUPABASE_URL}/rest/v1/project_documents"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            url,
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=doc,
        )
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(f"Supabase doc save {r.status_code}: {r.text[:200]}")


async def _sb_delete_doc(user_id: str, project_id: str, doc_id: str):
    url = (
        f"{SUPABASE_URL}/rest/v1/project_documents"
        f"?id=eq.{doc_id}&user_id=eq.{user_id}&project_id=eq.{project_id}"
    )
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.delete(url, headers=_sb_headers())
        r.raise_for_status()


# ── Public API ────────────────────────────────────────────────────

async def build_rag_context(user_id: str, project_id: str, query: str) -> str:
    """
    Retrieve the most relevant document snippets for a given query
    within a project. Returns a formatted string ready for prompt injection,
    or empty string if no documents exist.
    """
    if not project_id or not query:
        return ""

    docs = []

    if _use_supabase():
        try:
            docs = await _sb_list_docs(user_id, project_id)
        except Exception as e:
            print(f"document_service Supabase list failed: {e}")

    if not docs:
        docs = _local_list(user_id, project_id)

    if not docs:
        return ""

    # Score and sort by relevance
    scored = []
    for doc in docs:
        content = doc.get("content", "")
        score = _relevance(query, content)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Build context from top docs up to char limit
    parts = []
    total_chars = 0
    for score, doc in scored:
        if total_chars >= MAX_CONTEXT_CHARS:
            break
        content = doc.get("content", "")
        filename = doc.get("filename", "document")
        snippet = content[: MAX_CONTEXT_CHARS - total_chars]
        parts.append(f"[Document: {filename}]\n{snippet}")
        total_chars += len(snippet)

    if not parts:
        return ""

    return "[PROJECT DOCUMENTS]\n" + "\n\n---\n\n".join(parts) + "\n[/PROJECT DOCUMENTS]"


async def add_document(
    user_id: str,
    project_id: str,
    filename: str,
    content: str,
) -> dict:
    """Store a document in the project's knowledge base."""
    doc_id = hashlib.sha256(f"{user_id}{project_id}{filename}".encode()).hexdigest()[:16]
    doc = {
        "id": doc_id,
        "user_id": user_id,
        "project_id": project_id,
        "filename": filename,
        "content": content[:50000],  # cap at 50k chars per doc
        "created_at": time.time(),
    }
    if _use_supabase():
        try:
            await _sb_save_doc(doc)
            return doc
        except Exception as e:
            print(f"document_service save failed: {e}")
    _local_save(user_id, project_id, doc)
    return doc


async def list_documents(user_id: str, project_id: str) -> list:
    """List all documents in a project."""
    if _use_supabase():
        try:
            return await _sb_list_docs(user_id, project_id)
        except Exception:
            pass
    return _local_list(user_id, project_id)


async def delete_document(user_id: str, project_id: str, doc_id: str):
    """Remove a document from a project."""
    if _use_supabase():
        try:
            await _sb_delete_doc(user_id, project_id, doc_id)
        except Exception:
            pass
    _local_delete(user_id, project_id, doc_id)
