"""Database models for Ramad Command Assistant."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


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
