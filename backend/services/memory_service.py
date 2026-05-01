"""
Memory service with Supabase (persistent) + file fallback (local).
- If SUPABASE_URL and SUPABASE_KEY are set -> uses Supabase PostgreSQL (survives redeploys)
- Otherwise -> falls back to local JSON files (good for local dev)
"""

import os
import json
import time
from pathlib import Path
from typing import Optional
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_TABLE = "sessions"

MEMORY_DIR = Path(os.getenv("MEMORY_DIR", "./data/memory"))
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

MAX_CONTEXT_MESSAGES = 30


def _use_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


class MemoryService:

    async def _sb_get(self, session_id: str) -> Optional[dict]:
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?session_id=eq.{session_id}&select=*"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=_headers())
            r.raise_for_status()
            rows = r.json()
            return rows[0] if rows else None

    async def _sb_upsert(self, session_id: str, data: dict):
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
        payload = {
            "session_id": session_id,
            "messages": json.dumps(data["messages"]),
            "created_at": data.get("created_at", time.time()),
            "updated_at": time.time(),
        }
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                url,
                headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload
            )
            r.raise_for_status()

    async def _sb_delete(self, session_id: str):
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?session_id=eq.{session_id}"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(url, headers=_headers())
            r.raise_for_status()

    async def _sb_list(self) -> list:
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=session_id,messages,created_at,updated_at&order=updated_at.desc"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=_headers())
            r.raise_for_status()
            return r.json()

    def _file_path(self, session_id: str) -> Path:
        return MEMORY_DIR / f"{session_id}.json"

    def _file_load(self, session_id: str) -> dict:
        p = self._file_path(session_id)
        if p.exists():
            with open(p) as f:
                return json.load(f)
        return {"session_id": session_id, "messages": [], "created_at": time.time()}

    def _file_save(self, session_id: str, data: dict):
        with open(self._file_path(session_id), "w") as f:
            json.dump(data, f, indent=2)

    async def load_session(self, session_id: str) -> dict:
        if _use_supabase():
            try:
                row = await self._sb_get(session_id)
                if row:
                    messages = json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
                    return {"session_id": session_id, "messages": messages,
                            "created_at": row.get("created_at"), "updated_at": row.get("updated_at")}
            except Exception as e:
                print(f"Supabase read failed, using file: {e}")
        return self._file_load(session_id)

    async def add_message(self, session_id: str, role: str, content: str):
        data = await self.load_session(session_id)
        data["messages"].append({"role": role, "content": content, "timestamp": time.time()})
        if len(data["messages"]) > MAX_CONTEXT_MESSAGES * 2:
            data["messages"] = data["messages"][-MAX_CONTEXT_MESSAGES * 2:]
        data["updated_at"] = time.time()
        if _use_supabase():
            try:
                await self._sb_upsert(session_id, data)
                return
            except Exception as e:
                print(f"Supabase write failed, using file: {e}")
        self._file_save(session_id, data)

    async def get_context(self, session_id: str) -> list:
        data = await self.load_session(session_id)
        messages = data.get("messages", [])[-MAX_CONTEXT_MESSAGES:]
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def clear_session(self, session_id: str):
        if _use_supabase():
            try:
                await self._sb_delete(session_id)
            except Exception:
                pass
        p = self._file_path(session_id)
        if p.exists():
            p.unlink()

    async def list_sessions(self) -> list:
        if _use_supabase():
            try:
                rows = await self._sb_list()
                return [r["session_id"] for r in rows]
            except Exception:
                pass
        return [f.stem for f in MEMORY_DIR.glob("*.json")]

    async def get_session_summary(self, session_id: str) -> dict:
        data = await self.load_session(session_id)
        messages = data.get("messages", [])
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "preview": messages[-1]["content"][:80] + "..." if messages else "",
        }

    async def clear_all(self):
        sessions = await self.list_sessions()
        for s in sessions:
            await self.clear_session(s)


memory_service = MemoryService()
