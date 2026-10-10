"""Core domain models for Ramad Command Assistant."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class UnifiedMessage(BaseModel):
    user_id: str
    channel: str = "telegram"
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
