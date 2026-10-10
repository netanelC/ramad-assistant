import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.core.voice import IVoiceProcessor


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []
        self.downloaded_files: dict[str, bytes] = {
            "voice_456": b"SAMPLE_AUDIO_OGG_BYTES"
        }

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True

    async def download_file(self, file_id: str):
        return self.downloaded_files.get(file_id)


class StubVoiceProcessor(IVoiceProcessor):
    def __init__(self, simulated_text: str):
        self.simulated_text = simulated_text
        self.received_audio: list[bytes] = []

    async def process_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        self.received_audio.append(audio_bytes)
        return self.simulated_text


@pytest.mark.asyncio
async def test_voice_in_text_out_task_creation_e2e(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    spy_adapter = SpyTelegramAdapter()
    voice_processor = StubVoiceProcessor(simulated_text="תפתח משימה לתג\"ב מחר בצהריים: לבדוק שרתים")

    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
        voice_processor=voice_processor,
    )

    voice_payload = {
        "update_id": 10008,
        "message": {
            "message_id": 70,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "voice": {
                "file_id": "voice_456",
                "mime_type": "audio/ogg",
                "duration": 3
            }
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=voice_payload)

    assert response.status_code == 200
    assert len(voice_processor.received_audio) == 1
    assert voice_processor.received_audio[0] == b"SAMPLE_AUDIO_OGG_BYTES"

    # Task created in DB
    tasks = task_repo.list_tasks(status="OPEN")
    assert len(tasks) == 1
    assert "לבדוק שרתים" in tasks[0].title

    # Text response in Telegram (Voice-In / Text-Out)
    assert len(spy_adapter.sent_messages) == 1
    recipient_id, text_reply = spy_adapter.sent_messages[0]
    assert recipient_id == "999888"
    assert "נפתחה משימה חדשה" in text_reply
    assert "לבדוק שרתים" in text_reply
