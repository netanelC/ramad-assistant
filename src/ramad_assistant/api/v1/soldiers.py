"""Soldiers and Teams REST API Router."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ramad_assistant.db.models import Soldier, Team
from ramad_assistant.db.repository import TaskRepository


router = APIRouter(prefix="/api/v1", tags=["soldiers"])


def get_repo(request: Request) -> TaskRepository:
    return request.app.state.task_repo


# --- Request & Response Schemas ---
class SoldierCreateSchema(BaseModel):
    full_name: str
    team_id: Optional[int] = None
    service_type: str = "MANDATORY"
    rank: Optional[str] = None
    tash_status: Optional[str] = None
    academic_status: Optional[str] = None
    excellence_status: Optional[str] = None
    excellence_notes: Optional[str] = None
    release_date: Optional[str] = None
    current_naat: Optional[str] = None
    education: Optional[str] = None
    commander_notes: Optional[str] = None


class SoldierUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    team_id: Optional[int] = None
    service_type: Optional[str] = None
    rank: Optional[str] = None
    tash_status: Optional[str] = None
    academic_status: Optional[str] = None
    excellence_status: Optional[str] = None
    excellence_notes: Optional[str] = None
    release_date: Optional[str] = None
    current_naat: Optional[str] = None
    education: Optional[str] = None
    commander_notes: Optional[str] = None


class OneOnOneSchema(BaseModel):
    notes: str
    meeting_date: Optional[str] = None
    next_due_date: Optional[str] = None


class NaatAssignSchema(BaseModel):
    duty_name: str
    start_date: Optional[str] = None


class MentorshipSchema(BaseModel):
    personal_goal: str
    professional_goal: str
    contract_year: int = 2026
    notes: Optional[str] = None


# --- Teams Endpoints ---
@router.get("/teams")
async def list_teams(repo: TaskRepository = Depends(get_repo)) -> list[Team]:
    return repo.list_teams()


@router.get("/teams/summary")
async def get_section_summary(repo: TaskRepository = Depends(get_repo)) -> dict[str, Any]:
    return repo.get_section_summary()


# --- Soldiers Endpoints ---
@router.get("/soldiers")
async def list_soldiers(
    team_id: Optional[int] = None,
    service_type: Optional[str] = None,
    tash_status: Optional[str] = None,
    excellence_status: Optional[str] = None,
    upcoming_releases_days: Optional[int] = None,
    repo: TaskRepository = Depends(get_repo),
) -> list[Soldier]:
    if upcoming_releases_days:
        return repo.get_upcoming_releases(days_ahead=upcoming_releases_days)

    soldiers = repo.list_soldiers(team_id=team_id)

    if service_type:
        soldiers = [s for s in soldiers if s.service_type == service_type]
    if tash_status:
        soldiers = [s for s in soldiers if s.tash_status and s.tash_status.strip()]
    if excellence_status:
        soldiers = [s for s in soldiers if s.excellence_status and s.excellence_status.strip()]

    return soldiers


@router.post("/soldiers", status_code=201)
async def create_soldier(
    payload: SoldierCreateSchema,
    repo: TaskRepository = Depends(get_repo),
) -> Soldier:
    soldier = Soldier(**payload.model_dump())
    return repo.create_soldier(soldier)


@router.get("/soldiers/{soldier_id}")
async def get_soldier(
    soldier_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> Soldier:
    soldier = repo.get_soldier(soldier_id)
    if not soldier:
        raise HTTPException(status_code=404, detail="חייל לא נמצא")
    return soldier


@router.put("/soldiers/{soldier_id}")
async def update_soldier(
    soldier_id: int,
    payload: SoldierUpdateSchema,
    repo: TaskRepository = Depends(get_repo),
) -> Soldier:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = repo.update_soldier(soldier_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="חייל לא נמצא")
    return updated


@router.delete("/soldiers/{soldier_id}")
async def delete_soldier(
    soldier_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, str]:
    success = repo.delete_soldier(soldier_id)
    if not success:
        raise HTTPException(status_code=404, detail="חייל לא נמצא")
    return {"status": "deleted", "id": str(soldier_id)}


# --- Command Actions Endpoints ---
@router.post("/soldiers/{soldier_id}/one-on-one")
async def record_one_on_one(
    soldier_id: int,
    payload: OneOnOneSchema,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    soldier = repo.get_soldier(soldier_id)
    if not soldier:
        raise HTTPException(status_code=404, detail="חייל לא נמצא")

    res = repo.record_one_on_one_meeting(
        soldier_id=soldier_id,
        meeting_date=payload.meeting_date,
        notes=payload.notes,
    )
    return {"status": "recorded", "contract": res}


@router.post("/soldiers/{soldier_id}/naat")
async def assign_naat(
    soldier_id: int,
    payload: NaatAssignSchema,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    soldier = repo.get_soldier(soldier_id)
    if not soldier:
        raise HTTPException(status_code=404, detail="חייל לא נמצא")

    repo.assign_naat(soldier_id, payload.duty_name, start_date=payload.start_date)
    updated = repo.get_soldier(soldier_id)
    return {"status": "assigned", "soldier": updated}


@router.get("/soldiers/{soldier_id}/naat-history")
async def get_naat_history(
    soldier_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> list[dict[str, Any]]:
    return repo.get_naat_history(soldier_id)


@router.get("/soldiers/{soldier_id}/mentorship")
async def get_mentorship(
    soldier_id: int,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    contract = repo.get_mentorship_contract(soldier_id)
    if not contract:
        return {"status": "not_set", "soldier_id": soldier_id}
    return contract


@router.put("/soldiers/{soldier_id}/mentorship")
async def update_mentorship(
    soldier_id: int,
    payload: MentorshipSchema,
    repo: TaskRepository = Depends(get_repo),
) -> dict[str, Any]:
    res = repo.set_mentorship_goals(
        soldier_id=soldier_id,
        personal_goal=payload.personal_goal,
        professional_goal=payload.professional_goal,
        year=payload.contract_year,
        notes=payload.notes,
    )
    return {"status": "updated", "contract": res}
