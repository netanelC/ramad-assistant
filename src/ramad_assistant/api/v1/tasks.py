"""Tasks and Tagab REST API Router."""
from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ramad_assistant.core.datetime_utils import get_israel_now
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


router = APIRouter(prefix="/api/v1", tags=["tasks"])


def get_repo(request: Request) -> TaskRepository:
    return request.app.state.task_repo


class TaskCreateSchema(BaseModel):
    title: str
    details: Optional[str] = None
    tagab_at: str  # YYYY-MM-DD or YYYY-MM-DD HH:MM
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN"
    related_team_id: Optional[int] = None
    related_soldier_id: Optional[int] = None


class TaskUpdateSchema(BaseModel):
    title: Optional[str] = None
    details: Optional[str] = None
    tagab_at: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    related_team_id: Optional[int] = None
    related_soldier_id: Optional[int] = None


class TaskStatusSchema(BaseModel):
    status: str  # OPEN, DONE, CANCELLED


class TaskPostponeSchema(BaseModel):
    reason: str = Field(..., min_length=2, description="חובת רישום סיבה לדחיית תג\"ב")
    new_tagab_at: str  # YYYY-MM-DD HH:MM or ISO string


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = "OPEN",
    urgency: Optional[str] = None,  # "overdue", "today", "all"
    repo: TaskRepository = Depends(get_repo),
) -> list[PersonalTask]:
    tasks = repo.list_tasks(status=status)
    now_str = get_israel_now().strftime("%Y-%m-%d %H:%M")
    today_date = get_israel_now().strftime("%Y-%m-%d")

    if urgency == "overdue":
        # Overdue tasks: tagab_at < now and status is OPEN
        return [t for t in tasks if t.tagab_at < now_str]
    elif urgency == "today":
        # Due today
        return [t for t in tasks if t.tagab_at.startswith(today_date)]

    return tasks


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskCreateSchema,
    repo: TaskRepository = Depends(get_repo),
) -> PersonalTask:
    task = PersonalTask(**payload.model_dump())
    return repo.create_task(task)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> PersonalTask:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="משימה לא נמצאה")
    return task


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    payload: TaskUpdateSchema,
    repo: TaskRepository = Depends(get_repo),
) -> PersonalTask:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = repo.update_task(task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="משימה לא נמצאה")
    return updated


@router.put("/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    payload: TaskStatusSchema,
    repo: TaskRepository = Depends(get_repo),
) -> PersonalTask:
    updated = repo.update_task_status(task_id, payload.status.upper())
    if not updated:
        raise HTTPException(status_code=404, detail="משימה לא נמצאה")
    return updated


@router.post("/tasks/{task_id}/postpone")
async def postpone_task(
    task_id: int,
    payload: TaskPostponeSchema,
    repo: TaskRepository = Depends(get_repo),
) -> PersonalTask:
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="חובת רישום סיבה לדחיית תג\"ב")

    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="משימה לא נמצאה")

    updated = repo.postpone_task(task_id, payload.new_tagab_at, reason)
    return updated


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, str]:
    success = repo.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="משימה לא נמצאה")
    return {"status": "deleted", "id": str(task_id)}


@router.post("/tasks/complete-all")
async def complete_all_tasks(
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    count = repo.complete_all_tasks()
    return {"status": "all_completed", "count": count}


@router.delete("/tasks/delete-all")
async def delete_all_tasks(
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    count = repo.delete_all_tasks(status="OPEN")
    return {"status": "all_deleted", "count": count}
