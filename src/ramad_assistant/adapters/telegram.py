"""Telegram Bot API implementation of IMessengerAdapter."""
import logging
from typing import Any, Optional
import httpx

from ramad_assistant.adapters.base import IMessengerAdapter
from ramad_assistant.core.models import UnifiedMessage

logger = logging.getLogger(__name__)


class TelegramAdapter(IMessengerAdapter):
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_base_url = f"https://api.telegram.org/bot{bot_token}"

    async def parse_inbound(self, payload: dict[str, Any]) -> UnifiedMessage:
        message_data = payload.get("message") or payload.get("edited_message") or {}
        from_user = message_data.get("from") or {}
        user_id = str(from_user.get("id", ""))
        text = message_data.get("text")

        media_url: Optional[str] = None
        media_type: Optional[str] = None

        voice = message_data.get("voice")
        if voice:
            media_url = voice.get("file_id")
            media_type = voice.get("mime_type", "audio/ogg")

        return UnifiedMessage(
            user_id=user_id,
            channel="telegram",
            text=text,
            media_url=media_url,
            media_type=media_type,
        )

    async def send_message(self, recipient_id: str, text: str) -> bool:
        url = f"{self.api_base_url}/sendMessage"
        payload = {
            "chat_id": recipient_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error("Failed to send Telegram message to %s: %s", recipient_id, e)
            return False
