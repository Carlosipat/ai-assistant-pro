"""
Task Planner API — per-user task management stored in Supabase or file.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import hashlib, json, time, os
from pathlib import Path

router = APIRouter(tags=["tasks"])

TASKS_DIR = Path(os.getenv("MEMORY_DIR", "./data/memory")) / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

class Task(BaseModel):
    id: Optional[str] = None
    title: str
    description: str = ""
    priority: str = "medium"  # low, medium, high
    status: str = "todo"  # todo, in_progress, done
    due_date: Optional[str] = None
    tags: list[str] = []

def get_user_id(authorization: str = None) -> str:
    if not authorization:
        return "guest"
    token = authorization.replace("Bearer ", "")
    if not token or token == "null":
        return "guest"
    return hashlib.sha256(token.encode()).hexdigest()[:32]

def tasks_file(user_id: str) -> Path:
    return TASKS_DIR / f"{user_id}.json"

def load_tasks(user_id: str) -> list:
    f = tasks_file(user_id)
    if f.exists():
        with open(f) as fp:
            return json.load(fp)
    return []

def save_tasks(user_id: str, tasks: list):
    with open(tasks_file(user_id), "w") as fp:
        json.dump(tasks, fp, indent=2)

@router.get("/tasks")
async def get_tasks(authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    tasks = load_tasks(user_id)
    return {"tasks": tasks, "total": len(tasks)}

@router.post("/tasks")
async def create_task(task: Task, authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    tasks = load_tasks(user_id)
    task.id = str(int(time.time() * 1000))
    tasks.append(task.dict())
    save_tasks(user_id, tasks)
    return {"task": task.dict(), "message": "Task created"}

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, task: Task, authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    tasks = load_tasks(user_id)
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            task.id = task_id
            tasks[i] = task.dict()
            save_tasks(user_id, tasks)
            return {"task": task.dict(), "message": "Updated"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    tasks = load_tasks(user_id)
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(user_id, tasks)
    return {"message": "Deleted"}

@router.patch("/tasks/{task_id}/status")
async def update_status(task_id: str, status: str, authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    tasks = load_tasks(user_id)
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = status
            save_tasks(user_id, tasks)
            return {"message": "Status updated", "status": status}
    raise HTTPException(status_code=404, detail="Task not found")
