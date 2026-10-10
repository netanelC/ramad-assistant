from datetime import datetime, timedelta, timezone
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
async def test_record_one_on_one_meeting_via_chat(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    soldier = task_repo.create_soldier(
        Soldier(
            full_name="דניאל כהן",
            service_type="MANDATORY",
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    expected_next_due = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    payload = {
        "update_id": 10017,
        "message": {
            "message_id": 96,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "ביצעתי שיחת 1-על-1 עם דניאל כהן: דיברנו על יעדים אישיים והתקדמות במדור"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/webhook/telegram", json=payload)

    assert res.status_code == 200
    contract = task_repo.get_mentorship_contract(soldier_id=soldier.id, year=now.year)
    assert contract is not None
    assert contract["last_one_on_one_date"] == today_str
    assert contract["next_one_on_one_due"] == expected_next_due
    assert "דיברנו על יעדים אישיים" in contract["notes"]

    assert len(spy_adapter.sent_messages) == 1
    _, reply = spy_adapter.sent_messages[0]
    assert "תועדה שיחת 1-על-1" in reply
    assert "דניאל כהן" in reply
    assert expected_next_due in reply
