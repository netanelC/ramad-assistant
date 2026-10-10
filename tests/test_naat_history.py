import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.models import Soldier
from ramad_assistant.db.repository import TaskRepository


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_assign_naat_archives_previous_and_updates_profile(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    soldier = task_repo.create_soldier(
        Soldier(
            full_name="אורי לוי",
            service_type="MANDATORY",
            current_naat="קשר מדורי",
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    # 1. Assign new na'at via chat
    payload_assign = {
        "update_id": 10011,
        "message": {
            "message_id": 90,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "שבץ נע\"ת לאורי לוי: אחראי הדרכה"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/webhook/telegram", json=payload_assign)

    assert res1.status_code == 200
    soldier_after = task_repo.get_soldier(soldier.id)
    assert soldier_after.current_naat == "אחראי הדרכה"

    # Verify history in DB
    history = task_repo.get_naat_history(soldier.id)
    assert len(history) >= 2  # old and new
    assert any(h["duty_name"] == "קשר מדורי" and h["end_date"] is not None for h in history)
    assert any(h["duty_name"] == "אחראי הדרכה" and h["end_date"] is None for h in history)

    # 2. Query na'at history via chat
    payload_history = {
        "update_id": 10012,
        "message": {
            "message_id": 91,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "היסטוריית נע\"ת אורי לוי"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post("/webhook/telegram", json=payload_history)

    assert res2.status_code == 200
    assert len(spy_adapter.sent_messages) == 2
    _, reply_history = spy_adapter.sent_messages[1]
    assert "היסטוריית נע\"ת" in reply_history
    assert "אורי לוי" in reply_history
    assert "קשר מדורי" in reply_history
    assert "אחראי הדרכה" in reply_history
