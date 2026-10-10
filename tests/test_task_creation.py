import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.repository import TaskRepository


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_natural_language_task_creation_e2e(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    payload = {
        "update_id": 10002,
        "message": {
            "message_id": 50,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "תפתח משימה לתג\"ב מחר בצהריים: לבדוק ביצועים מול צוות 1"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify task was saved in the database
    tasks = task_repo.list_tasks(status="OPEN")
    assert len(tasks) == 1
    task = tasks[0]
    assert "לבדוק ביצועים מול צוות 1" in task.title
    assert task.tagab_at is not None
    assert task.status == "OPEN"

    # Verify confirmation sent back via Telegram
    assert len(spy_adapter.sent_messages) == 1
    recipient_id, reply_text = spy_adapter.sent_messages[0]
    assert recipient_id == "999888"
    assert "נפתחה משימה" in reply_text
    assert "תג\"ב" in reply_text
