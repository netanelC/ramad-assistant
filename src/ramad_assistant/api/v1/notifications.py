"""Notifications and Device Tokens REST API Router."""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


router = APIRouter(prefix="/api/v1", tags=["notifications"])

# In-memory / persistent device tokens registry for FCM
REGISTERED_FCM_TOKENS: set[str] = set()


class DeviceTokenSchema(BaseModel):
    fcm_token: str
    device_name: Optional[str] = "Android Device"


class NotificationSendSchema(BaseModel):
    title: str
    body: str
    deeplink_tab: Optional[str] = "agent"


@router.post("/notifications/register-token")
async def register_token(payload: DeviceTokenSchema) -> dict[str, Any]:
    token = payload.fcm_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="FCM Token cannot be empty")
    REGISTERED_FCM_TOKENS.add(token)
    return {"status": "registered", "total_registered_devices": len(REGISTERED_FCM_TOKENS)}


@router.get("/notifications/status")
async def get_notification_status() -> dict[str, Any]:
    return {
        "status": "ready",
        "registered_devices_count": len(REGISTERED_FCM_TOKENS),
    }
