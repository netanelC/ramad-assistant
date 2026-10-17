import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.core.voice import IVoiceProcessor


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

    voice_processor = StubVoiceProcessor(simulated_text="תפתח משימה לתג\"ב מחר בצהריים: לבדוק שרתים")

    app = create_app(
        task_repo=task_repo,
        voice_processor=voice_processor,
    )

    files = {"file": ("recording.ogg", b"SAMPLE_AUDIO_OGG_BYTES", "audio/ogg")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/voice/chat", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcription"] == "תפתח משימה לתג\"ב מחר בצהריים: לבדוק שרתים"
    reply_text = data["response_text"]
    assert "נפתחה משימה" in reply_text or "פתחתי" in reply_text or "נוצרה" in reply_text
    assert "לבדוק שרתים" in reply_text

    # Action cards should also be present for task creation
    assert any(card["card_type"] == "task" and card["action"] == "created" for card in data["action_cards"])

    assert len(voice_processor.received_audio) == 1
    assert voice_processor.received_audio[0] == b"SAMPLE_AUDIO_OGG_BYTES"

    # Task created in DB
    tasks = task_repo.list_tasks(status="OPEN")
    assert len(tasks) == 1
    assert "לבדוק שרתים" in tasks[0].title
