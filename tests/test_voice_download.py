import pytest
import httpx

from ramad_assistant.adapters.telegram import TelegramAdapter


@pytest.mark.asyncio
async def test_telegram_voice_message_parsing_and_download(respx_mock=None):
    # Mock Telegram Bot API endpoints using custom handler or transport
    bot_token = "test-token"
    adapter = TelegramAdapter(bot_token=bot_token)

    # Mock getFile and download response
    async def mock_transport(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "getFile" in url_str:
            return httpx.Response(
                status_code=200,
                json={"ok": True, "result": {"file_id": "voice_123", "file_path": "voice/audio.oga"}}
            )
        elif "voice/audio.oga" in url_str:
            return httpx.Response(status_code=200, content=b"OGG_OPUS_SAMPLE_AUDIO_DATA")
        elif "sendMessage" in url_str:
            return httpx.Response(status_code=200, json={"ok": True})
        return httpx.Response(status_code=404)

    adapter.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))

    voice_payload = {
        "update_id": 10007,
        "message": {
            "message_id": 60,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "voice": {
                "file_id": "voice_123",
                "mime_type": "audio/ogg",
                "duration": 4
            }
        }
    }

    unified = await adapter.parse_inbound(voice_payload)
    assert unified.media_url == "voice_123"
    assert unified.media_type == "audio/ogg"

    # Download raw audio bytes
    audio_bytes = await adapter.download_file("voice_123")
    assert audio_bytes == b"OGG_OPUS_SAMPLE_AUDIO_DATA"


@pytest.mark.asyncio
async def test_telegram_voice_download_error_handling():
    bot_token = "test-token"
    adapter = TelegramAdapter(bot_token=bot_token)

    async def mock_error_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, json={"ok": False, "description": "Internal error"})

    adapter.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_error_transport))

    audio_bytes = await adapter.download_file("nonexistent_id")
    assert audio_bytes is None
