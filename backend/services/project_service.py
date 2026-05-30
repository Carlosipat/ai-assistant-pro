
"""
services/project_service.py — Retrai v6
Full project management: name, description, system_prompt, sources (text/url/file).
Supabase-backed with local JSON fallback.
"""
import os, json, time, uuid as _uuid
from pathlib import Path
from typing import Optional
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
MEMORY_DIR   = Path(os.getenv("MEMORY_DIR", "/tmp/memory"))


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def _use_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)

# ── Local file helpers ────────────────────────────────────────────

def _projects_dir(user_id: str) -> Path:
    p = MEMORY_DIR / user_id / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _file_get(user_id: str, project_id: str) -> Optional[dict]:
    p = _projects_dir(user_id) / f"{project_id}.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None

def _file_list(user_id: str) -> list:
    d = _projects_dir(user_id)
    result = []
    for f in d.glob("*.json"):
        try:
            with open(f) as fp:
                result.append(json.load(fp))
        except Exception:
            pass
    result.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return result

def _file_save(user_id: str, project: dict):
    p = _projects_dir(user_id) / f"{project['id']}.json"
    with open(p, "w") as f:
        json.dump(project, f, indent=2)

def _file_delete(user_id: str, project_id: str):
    p = _projects_dir(user_id) / f"{project_id}.json"
    if p.exists():
        p.unlink()

# ── Supabase helpers ──────────────────────────────────────────────

async def _sb_get_project(user_id: str, project_id: str) -> Optional[dict]:
    url = f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}&user_id=eq.{user_id}&select=*"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=_sb_headers())
        r.raise_for_status()
        rows = r.json()
        if rows:
            row = rows[0]
            # Defensive: normalise sources in case an old TEXT row comes back
            if isinstance(row.get("sources"), str):
                row["sources"] = json.loads(row["sources"])
            return row
    return None


async def _sb_list_projects(user_id: str) -> list:
    url = (
        f"{SUPABASE_URL}/rest/v1/projects"
        f"?user_id=eq.{user_id}&select=*&order=updated_at.desc"
    )
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=_sb_headers())
        r.raise_for_status()
        rows = r.json()
        for row in rows:
            # Defensive: normalise sources in case an old TEXT row comes back
            if isinstance(row.get("sources"), str):
                row["sources"] = json.loads(row["sources"])
        return rows

async def _sb_upsert_project(user_id: str, project: dict) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/projects"
    payload = {**project, "user_id": user_id, "updated_at": time.time()}
    # sources is JSONB in Supabase — send as native list, never as a string
    if isinstance(payload.get("sources"), str):
        payload["sources"] = json.loads(payload["sources"])
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            url,
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()[0] if r.json() else payload
        # Defensive: normalise sources in case an old TEXT row comes back
        if isinstance(result.get("sources"), str):
            result["sources"] = json.loads(result["sources"])
        return result

async def _sb_delete_project(user_id: str, project_id: str):
    url = f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}&user_id=eq.{user_id}"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.delete(url, headers=_sb_headers())
        r.raise_for_status()

# ── Public API ────────────────────────────────────────────────────

async def get_project_context(user_id: str, project_id: str) -> str:
    """Return formatted context string for injection into model prompt."""
    if not project_id:
        return ""
    project = None
    if _use_supabase():
        try:
            project = await _sb_get_project(user_id, project_id)
        except Exception as e:
            print(f"project_service Supabase read failed: {e}")
    if project is None:
        project = _file_get(user_id, project_id)
    if not project:
        return ""
    parts = []
    name = project.get("name", "").strip()
    desc = (project.get("description") or project.get("system_prompt", "")).strip()
    if name:
        parts.append(f"Project: {name}")
    if desc:
        parts.append(desc)
    # Embed text sources directly
    for src in project.get("sources", []):
        if src.get("type") in ("text", "file") and src.get("content"):
            label = src.get("label", "Source")
            parts.append(f"[{label}]\n{src['content'][:3000]}")
    return "\n\n".join(parts)

async def list_projects(user_id: str) -> list:
    if _use_supabase():
        try:
            return await _sb_list_projects(user_id)
        except Exception as e:
            print(f"project_service list failed: {e}")
    return _file_list(user_id)

async def create_project(user_id: str, name: str, description: str = "", system_prompt: str = "") -> dict:
    project = {
        "id": str(_uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "description": description,
        "system_prompt": system_prompt or description,
        "sources": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    if _use_supabase():
        try:
            return await _sb_upsert_project(user_id, project)
        except Exception as e:
            print(f"project_service create failed: {e}")
    _file_save(user_id, project)
    return project

async def update_project(user_id: str, project_id: str, updates: dict) -> Optional[dict]:
    project = None
    if _use_supabase():
        try:
            project = await _sb_get_project(user_id, project_id)
        except Exception:
            pass
    if project is None:
        project = _file_get(user_id, project_id)
    if not project:
        return None
    project.update({**updates, "updated_at": time.time()})
    if "description" in updates:
        project["system_prompt"] = updates["description"]
    if _use_supabase():
        try:
            return await _sb_upsert_project(user_id, project)
        except Exception:
            pass
    _file_save(user_id, project)
    return project

async def delete_project(user_id: str, project_id: str):
    if _use_supabase():
        try:
            await _sb_delete_project(user_id, project_id)
        except Exception:
            pass
    _file_delete(user_id, project_id)

async def add_source(user_id: str, project_id: str, source: dict) -> Optional[dict]:
    """Add a source to a project's sources list."""
    project = None
    if _use_supabase():
        try:
            project = await _sb_get_project(user_id, project_id)
        except Exception:
            pass
    if project is None:
        project = _file_get(user_id, project_id)
    if not project:
        return None
    source["id"] = str(_uuid.uuid4())[:8]
    source["created_at"] = time.time()
    project.setdefault("sources", []).append(source)
    project["updated_at"] = time.time()
    if _use_supabase():
        try:
            return await _sb_upsert_project(user_id, project)
        except Exception:
            pass
    _file_save(user_id, project)
    return project

async def remove_source(user_id: str, project_id: str, source_id: str) -> Optional[dict]:
    """Remove a source from a project."""
    project = None
    if _use_supabase():
        try:
            project = await _sb_get_project(user_id, project_id)
        except Exception:
            pass
    if project is None:
        project = _file_get(user_id, project_id)
    if not project:
        return None
    project["sources"] = [s for s in project.get("sources", []) if s.get("id") != source_id]
    project["updated_at"] = time.time()
    if _use_supabase():
        try:
            return await _sb_upsert_project(user_id, project)
        except Exception:
            pass
    _file_save(user_id, project)
    return project
