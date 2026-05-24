"""
Memory / sessions router — scoped per user.
All endpoints require a valid user token (or fall back to guest).
"""
from fastapi import APIRouter, HTTPException, Header
from services.memory_service import memory_service
from routers.auth import _get_user_id

router = APIRouter(tags=["memory"])


def _uid(authorization: str | None) -> str:
    """Extract user_id from token, fall back to 'guest'."""
    if not authorization:
        return "guest"
    try:
        uid = _get_user_id(authorization.replace("Bearer ", ""))
        return uid or "guest"
    except Exception:
        return "guest"


# ── Sessions ──────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(authorization: str = Header(None)):
    user_id = _uid(authorization)
    sessions = await memory_service.list_sessions(user_id)
    summaries = [
        await memory_service.get_session_summary(s, user_id) for s in sessions
    ]
    summaries.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
    return {"sessions": summaries, "total": len(summaries)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, authorization: str = Header(None)):
    user_id = _uid(authorization)
    data = await memory_service.load_session(session_id, user_id)
    if not data["messages"]:
        raise HTTPException(status_code=404, detail="Session not found or empty")
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, authorization: str = Header(None)):
    user_id = _uid(authorization)
    await memory_service.clear_session(session_id, user_id)
    return {"message": f"Session {session_id} deleted"}


@router.delete("/sessions")
async def clear_all_sessions(authorization: str = Header(None)):
    user_id = _uid(authorization)
    await memory_service.clear_all(user_id)
    return {"message": "All sessions cleared"}


# ── User Settings ─────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(authorization: str = Header(None)):
    user_id = _uid(authorization)
    if user_id == "guest":
        return {}
    return await memory_service.get_settings(user_id)


@router.post("/settings")
async def save_settings(body: dict, authorization: str = Header(None)):
    user_id = _uid(authorization)
    if user_id == "guest":
        raise HTTPException(status_code=401, detail="Login to save settings")
    return await memory_service.save_settings(user_id, body)
