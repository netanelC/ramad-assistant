"""Voice processing pipeline using Gemini multimodal audio capabilities."""
import base64
import logging
import os
from abc import ABC, abstractmethod
import httpx

logger = logging.getLogger(__name__)


class IVoiceProcessor(ABC):
    @abstractmethod
    async def process_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Processes raw audio bytes and returns transcribed/interpreted text."""
        pass


class GeminiVoiceProcessor(IVoiceProcessor):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    async def process_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY configured; returning empty transcript.")
            return ""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded_audio,
                            }
                        },
                        {
                            "text": (
                                "תמלל במדויק את הודעת השמע בעברית. "
                                "החזר אך ורק את התמלול המדויק ללא שום מילות הסבר או תוספות."
                            )
                        },
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                logger.error("Gemini API audio error: %d %s", response.status_code, response.text)
                return ""
        except Exception as e:
            logger.error("Failed to process audio with Gemini: %s", e)
            return ""
