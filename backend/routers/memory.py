from fastapi import APIRouter, HTTPException
from services.memory_service import memory_service

router = APIRouter(tags=["memory"])


@router.get("/sessions")
async def list_sessions():
    sessions = await memory_service.list_sessions()
    summaries = [await memory_service.get_session_summary(s) for s in sessions]
    summaries.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
    return {"sessions": summaries, "total": len(summaries)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    data = await memory_service.load_session(session_id)
    if not data["messages"]:
        raise HTTPException(status_code=404, detail="Session not found or empty")
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await memory_service.clear_session(session_id)
    return {"message": f"Session {session_id} deleted"}


@router.delete("/sessions")
async def clear_all_sessions():
    await memory_service.clear_all()
    return {"message": "All sessions cleared"}
