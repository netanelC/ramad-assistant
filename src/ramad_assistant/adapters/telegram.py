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
        self.file_base_url = f"https://api.telegram.org/file/bot{bot_token}"
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is not None:
            return self.http_client
        return httpx.AsyncClient()

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
            client = await self._get_client()
            response = await client.post(url, json=payload, timeout=10.0)
            return response.status_code == 200
        except Exception as e:
            logger.error("Failed to send Telegram message to %s: %s", recipient_id, e)
            return False

    async def download_file(self, file_id: str) -> Optional[bytes]:
        url = f"{self.api_base_url}/getFile?file_id={file_id}"
        try:
            client = await self._get_client()
            res = await client.get(url, timeout=15.0)
            if res.status_code != 200:
                logger.error("Telegram getFile returned status %d", res.status_code)
                return None
            data = res.json()
            if not data.get("ok") or not data.get("result"):
                return None
            file_path = data["result"].get("file_path")
            if not file_path:
                return None

            download_url = f"{self.file_base_url}/{file_path}"
            file_res = await client.get(download_url, timeout=30.0)
            if file_res.status_code != 200:
                return None
            return file_res.content
        except Exception as e:
            logger.error("Failed to download file %s: %s", file_id, e)
            return None
