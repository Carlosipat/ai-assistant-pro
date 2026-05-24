"""
routers/projects.py — Retrai v6
Full CRUD for projects + sources (text, URL, file upload).
"""
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Header
from routers.auth import _get_user_id
from services.project_service import (
    list_projects, create_project, update_project,
    delete_project, add_source, remove_source, _file_get, _use_supabase, _sb_get_project
)
from services.file_service import parse_file

router = APIRouter(tags=["projects"])


def _uid(authorization: str | None) -> str:
    if not authorization:
        return "guest"
    try:
        uid = _get_user_id(authorization.replace("Bearer ", ""))
        return uid or "guest"
    except Exception:
        return "guest"


def _fmt(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "name": p.get("name", ""),
        "description": p.get("description") or p.get("system_prompt", ""),
        "sources": p.get("sources", []),
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


# ── Projects CRUD ─────────────────────────────────────────────────

@router.get("/projects")
async def list_projects_route(authorization: str = Header(None)):
    user_id = _uid(authorization)
    projects = await list_projects(user_id)
    return {"projects": [_fmt(p) for p in projects]}


@router.post("/projects")
async def create_project_route(body: dict, authorization: str = Header(None)):
    user_id = _uid(authorization)
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name required")
    description = body.get("description", body.get("system_prompt", ""))
    project = await create_project(user_id, name, description)
    return {"project": _fmt(project)}


@router.get("/projects/{project_id}")
async def get_project_route(project_id: str, authorization: str = Header(None)):
    user_id = _uid(authorization)
    project = None
    if _use_supabase():
        try:
            project = await _sb_get_project(user_id, project_id)
        except Exception:
            pass
    if project is None:
        project = _file_get(user_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": _fmt(project)}


@router.put("/projects/{project_id}")
async def update_project_route(project_id: str, body: dict, authorization: str = Header(None)):
    user_id = _uid(authorization)
    project = await update_project(user_id, project_id, body)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": _fmt(project)}


@router.delete("/projects/{project_id}")
async def delete_project_route(project_id: str, authorization: str = Header(None)):
    user_id = _uid(authorization)
    await delete_project(user_id, project_id)
    return {"message": "Project deleted"}


# ── Sources ───────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sources")
async def add_source_route(project_id: str, body: dict, authorization: str = Header(None)):
    user_id = _uid(authorization)
    src_type = "url" if body.get("url") else "text"
    content  = body.get("url") if src_type == "url" else body.get("text", "")
    label    = body.get("title") or body.get("label") or src_type
    if not content:
        raise HTTPException(status_code=400, detail="Source content or URL required")
    source = {"type": src_type, "label": label, "content": content}
    if src_type == "url":
        source["url"] = body.get("url")
    project = await add_source(user_id, project_id, source)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": _fmt(project), "message": "Source added"}


@router.delete("/projects/{project_id}/sources/{source_id}")
async def remove_source_route(project_id: str, source_id: str, authorization: str = Header(None)):
    user_id = _uid(authorization)
    project = await remove_source(user_id, project_id, source_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": _fmt(project), "message": "Source removed"}


@router.post("/projects/{project_id}/sources/upload")
async def upload_source_route(
    project_id: str,
    file: UploadFile = File(...),
    label: str = Form(default=""),
    authorization: str = Header(None),
):
    user_id = _uid(authorization)
    try:
        file_bytes = await file.read()
        extracted_text, image_b64, mime_type = parse_file(file.filename, file_bytes)
        if image_b64:
            raise HTTPException(status_code=400, detail="Images cannot be added as project sources. Upload text files (PDF, DOCX, TXT, CSV).")
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in file.")
        source = {
            "type": "file",
            "label": label or file.filename,
            "content": extracted_text[:10000],
            "filename": file.filename,
            "size": len(file_bytes),
        }
        project = await add_source(user_id, project_id, source)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        chars = len(extracted_text)
        return {
            "project": _fmt(project),
            "message": f"File '{file.filename}' added ({chars:,} chars extracted)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")
