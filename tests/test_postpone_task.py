import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_postpone_task_with_reason_updates_db_and_confirms(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    saved_task = task_repo.create_task(
        PersonalTask(
            title="שיחה עם צוות אלגוריתמים",
            tagab_at="2026-10-11 10:00",
            priority="HIGH",
            status="OPEN",
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    payload = {
        "update_id": 10005,
        "message": {
            "message_id": 53,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": f"תדחה משימה #{saved_task.id} למחר בערב בגלל בלת\"ם מבצעי"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    task_after = task_repo.get_task(saved_task.id)
    assert task_after.postpone_count == 1
    assert task_after.last_postpone_reason == "בלת\"ם מבצעי"
    assert task_after.status == "POSTPONED"

    assert len(spy_adapter.sent_messages) == 1
    _, reply_text = spy_adapter.sent_messages[0]
    assert "נדחתה" in reply_text
    assert "בלת\"ם מבצעי" in reply_text
    assert "דחייה מספר 1" in reply_text


@pytest.mark.asyncio
async def test_postpone_without_reason_is_rejected(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    saved_task = task_repo.create_task(
        PersonalTask(
            title="שיחה עם צוות אלגוריתמים",
            tagab_at="2026-10-11 10:00",
            priority="HIGH",
            status="OPEN",
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    payload = {
        "update_id": 10006,
        "message": {
            "message_id": 54,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": f"תדחה משימה #{saved_task.id} למחר בערב"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    task_after = task_repo.get_task(saved_task.id)
    assert task_after.postpone_count == 0  # Not postponed!

    assert len(spy_adapter.sent_messages) == 1
    _, reply_text = spy_adapter.sent_messages[0]
    assert "סיבה" in reply_text
