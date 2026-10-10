"""Database models for Ramad Command Assistant."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Team(BaseModel):
    id: Optional[int] = None
    name: str
    team_lead_name: Optional[str] = None
    description: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Soldier(BaseModel):
    id: Optional[int] = None
    full_name: str
    team_id: Optional[int] = None
    service_type: str = "MANDATORY"  # MANDATORY, CAREER, RESERVE, CONSULTANT
    release_date: Optional[str] = None  # YYYY-MM-DD
    current_naat: Optional[str] = None
    education: Optional[str] = None
    commander_notes: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MentorshipContract(BaseModel):
    id: Optional[int] = None
    soldier_id: int
    contract_year: int = 2026
    personal_goal: str
    professional_goal: str
    last_one_on_one_date: Optional[str] = None
    next_one_on_one_due: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PersonalTask(BaseModel):
    id: Optional[int] = None
    title: str
    details: Optional[str] = None
    tagab_at: str  # ISO 8601 string or date
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN"  # OPEN, DONE, CANCELLED, POSTPONED
    related_team_id: Optional[int] = None
    related_soldier_id: Optional[int] = None
    postpone_count: int = 0
    last_postpone_reason: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ReflectionLog(BaseModel):
    id: Optional[int] = None
    session_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    q1_automation_answer: Optional[str] = None
    q2_resolve_answer: Optional[str] = None
    q3_people_answer: Optional[str] = None
    points_to_preserve: list[str] = Field(default_factory=list)
    points_to_improve: list[str] = Field(default_factory=list)
    summary_insights: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

