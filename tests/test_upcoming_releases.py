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
async def test_upcoming_releases_filtering_and_chat_query(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    now = datetime.now(timezone.utc)
    date_45d = (now + timedelta(days=45)).strftime("%Y-%m-%d")
    date_120d = (now + timedelta(days=120)).strftime("%Y-%m-%d")
    date_300d = (now + timedelta(days=300)).strftime("%Y-%m-%d")

    # Soldier 1: releases in 45 days
    task_repo.create_soldier(
        Soldier(
            full_name="אלון מזרחי",
            service_type="MANDATORY",
            release_date=date_45d,
        )
    )
    # Soldier 2: releases in 120 days
    task_repo.create_soldier(
        Soldier(
            full_name="נועה שחר",
            service_type="CAREER",
            release_date=date_120d,
        )
    )
    # Soldier 3: releases in 300 days
    task_repo.create_soldier(
        Soldier(
            full_name="תומר גל",
            service_type="MANDATORY",
            release_date=date_300d,
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    # 1. Query 3 months (90 days)
    payload_90d = {
        "update_id": 10013,
        "message": {
            "message_id": 92,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "מי משתחרר ב-3 החודשים הקרובים?"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/webhook/telegram", json=payload_90d)

    assert res1.status_code == 200
    assert len(spy_adapter.sent_messages) == 1
    _, reply_90d = spy_adapter.sent_messages[0]
    assert "משתחררים" in reply_90d
    assert "אלון מזרחי" in reply_90d
    assert "נועה שחר" not in reply_90d
    assert "תומר גל" not in reply_90d

    # 2. Query 6 months (180 days)
    payload_180d = {
        "update_id": 10014,
        "message": {
            "message_id": 93,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "מי משתחרר ב-6 החודשים הקרובים?"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post("/webhook/telegram", json=payload_180d)

    assert res2.status_code == 200
    assert len(spy_adapter.sent_messages) == 2
    _, reply_180d = spy_adapter.sent_messages[1]
    assert "אלון מזרחי" in reply_180d
    assert "נועה שחר" in reply_180d
    assert "תומר גל" not in reply_180d
