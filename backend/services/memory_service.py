"""
Memory service — Supabase (persistent) with user_id isolation.
Every session is now scoped to a user_id so users never see
each other's conversations.
Fallback: local JSON files (good for dev, partitioned by user).
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
SETTINGS_TABLE = "user_settings"

MEMORY_DIR = Path(os.getenv("MEMORY_DIR", "./data/memory"))
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

MAX_CONTEXT_MESSAGES = 30

GUEST_USER = "guest"


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

    # ── Supabase session ops ─────────────────────────────────────

    async def _sb_get(self, session_id: str, user_id: str) -> Optional[dict]:
        url = (
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
            f"?session_id=eq.{session_id}&user_id=eq.{user_id}&select=*"
        )
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=_headers())
            r.raise_for_status()
            rows = r.json()
            return rows[0] if rows else None

    async def _sb_upsert(self, session_id: str, user_id: str, data: dict):
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "title": data.get("title", "New Chat"),
            "messages": json.dumps(data["messages"]),
            "created_at": data.get("created_at", time.time()),
            "updated_at": time.time(),
        }
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                url,
                headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload,
            )
            if r.status_code not in (200, 201, 204):
                raise RuntimeError(f"Supabase upsert {r.status_code}: {r.text[:200]}")

    async def _sb_delete(self, session_id: str, user_id: str):
        url = (
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
            f"?session_id=eq.{session_id}&user_id=eq.{user_id}"
        )
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(url, headers=_headers())
            r.raise_for_status()

    async def _sb_list(self, user_id: str) -> list:
        url = (
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
            f"?user_id=eq.{user_id}"
            f"&select=session_id,title,messages,created_at,updated_at"
            f"&order=updated_at.desc"
        )
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=_headers())
            r.raise_for_status()
            return r.json()

    async def _sb_delete_all(self, user_id: str):
        url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?user_id=eq.{user_id}"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(url, headers=_headers())
            r.raise_for_status()

    # ── Local file ops (dev fallback) ───────────────────────────

    def _file_dir(self, user_id: str) -> Path:
        p = MEMORY_DIR / user_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _file_path(self, session_id: str, user_id: str) -> Path:
        return self._file_dir(user_id) / f"{session_id}.json"

    def _file_load(self, session_id: str, user_id: str) -> dict:
        p = self._file_path(session_id, user_id)
        if p.exists():
            with open(p) as f:
                return json.load(f)
        return {
            "session_id": session_id,
            "user_id": user_id,
            "title": "New Chat",
            "messages": [],
            "created_at": time.time(),
        }

    def _file_save(self, session_id: str, user_id: str, data: dict):
        with open(self._file_path(session_id, user_id), "w") as f:
            json.dump(data, f, indent=2)

    # ── Public API ───────────────────────────────────────────────

    async def load_session(self, session_id: str, user_id: str = GUEST_USER) -> dict:
        if _use_supabase():
            try:
                row = await self._sb_get(session_id, user_id)
                if row:
                    messages = (
                        json.loads(row["messages"])
                        if isinstance(row["messages"], str)
                        else row["messages"]
                    )
                    return {
                        "session_id": session_id,
                        "user_id": user_id,
                        "title": row.get("title", "New Chat"),
                        "messages": messages,
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                    }
            except Exception as e:
                print(f"Supabase read failed, using file: {e}")
        return self._file_load(session_id, user_id)

    async def add_message(
        self, session_id: str, role: str, content: str, user_id: str = GUEST_USER
    ):
        data = await self.load_session(session_id, user_id)
        data["messages"].append({"role": role, "content": content, "timestamp": time.time()})
        if len(data["messages"]) > MAX_CONTEXT_MESSAGES * 2:
            data["messages"] = data["messages"][-MAX_CONTEXT_MESSAGES * 2:]
        data["updated_at"] = time.time()
        # Auto-title from first user message
        if data.get("title", "New Chat") == "New Chat":
            first_user = next(
                (m["content"] for m in data["messages"] if m["role"] == "user"), None
            )
            if first_user:
                data["title"] = first_user[:60]
        if _use_supabase():
            try:
                await self._sb_upsert(session_id, user_id, data)
                return
            except Exception as e:
                print(f"Supabase write failed, using file: {e}")
        self._file_save(session_id, user_id, data)

    async def get_context(self, session_id: str, user_id: str = GUEST_USER) -> list:
        data = await self.load_session(session_id, user_id)
        messages = data.get("messages", [])[-MAX_CONTEXT_MESSAGES:]
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def clear_session(self, session_id: str, user_id: str = GUEST_USER):
        if _use_supabase():
            try:
                await self._sb_delete(session_id, user_id)
            except Exception:
                pass
        p = self._file_path(session_id, user_id)
        if p.exists():
            p.unlink()

    async def list_sessions(self, user_id: str = GUEST_USER) -> list:
        if _use_supabase():
            try:
                rows = await self._sb_list(user_id)
                return [r["session_id"] for r in rows]
            except Exception:
                pass
        d = self._file_dir(user_id)
        return [f.stem for f in d.glob("*.json")]

    async def get_session_summary(self, session_id: str, user_id: str = GUEST_USER) -> dict:
        data = await self.load_session(session_id, user_id)
        messages = data.get("messages", [])
        last = messages[-1]["content"] if messages else ""
        return {
            "session_id": session_id,
            "title": data.get("title", "New Chat"),
            "message_count": len(messages),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "preview": last[:80] + ("..." if len(last) > 80 else ""),
        }

    async def clear_all(self, user_id: str = GUEST_USER):
        if _use_supabase():
            try:
                await self._sb_delete_all(user_id)
                return
            except Exception:
                pass
        sessions = await self.list_sessions(user_id)
        for s in sessions:
            await self.clear_session(s, user_id)

    # ── Settings ─────────────────────────────────────────────────

    async def get_settings(self, user_id: str) -> dict:
        defaults = {
            "user_id": user_id,
            "display_name": "",
            "theme": "dark",
            "font_size": "medium",
            "language": "en",
            "ai_persona": "retrai",
            "ai_tone": "balanced",
            "max_tokens": 1024,
            "send_on_enter": True,
            "show_avatars": True,
            "compact_mode": False,
            "notifications": True,
        }
        if _use_supabase():
            try:
                url = (
                    f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}"
                    f"?user_id=eq.{user_id}&select=*"
                )
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(url, headers=_headers())
                    r.raise_for_status()
                    rows = r.json()
                    if rows:
                        return {**defaults, **rows[0]}
            except Exception as e:
                print(f"Settings read failed: {e}")
        # File fallback
        p = MEMORY_DIR / user_id / "settings.json"
        if p.exists():
            with open(p) as f:
                return {**defaults, **json.load(f)}
        return defaults

    # Columns that exist in the user_settings table (must match supabase_setup.sql)
    _SETTINGS_COLUMNS = {
        "user_id", "display_name", "theme", "font_size", "language",
        "ai_persona", "ai_tone", "max_tokens", "send_on_enter",
        "show_avatars", "compact_mode", "notifications", "updated_at",
    }

    async def save_settings(self, user_id: str, settings: dict) -> dict:
        settings["user_id"] = user_id
        settings["updated_at"] = time.time()
        # Only send columns the table actually has — prevents 400 on unknown keys
        safe_payload = {k: v for k, v in settings.items() if k in self._SETTINGS_COLUMNS}
        if _use_supabase():
            try:
                url = f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}"
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.post(
                        url,
                        headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                        json=safe_payload,
                    )
                    if r.status_code not in (200, 201, 204):
                        raise RuntimeError(f"Settings save {r.status_code}: {r.text[:200]}")
                return settings
            except Exception as e:
                print(f"Settings save failed: {e}")
        # File fallback
        p = MEMORY_DIR / user_id / "settings.json"
        (MEMORY_DIR / user_id).mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(settings, f, indent=2)
        return settings


memory_service = MemoryService()
