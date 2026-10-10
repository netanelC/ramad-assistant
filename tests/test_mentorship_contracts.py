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
async def test_mentorship_contract_creation_and_query_via_chat(tmp_path):
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

    # 1. Update mentorship contract goals via chat
    payload_update = {
        "update_id": 10015,
        "message": {
            "message_id": 94,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "עדכן חוזה חניכה לדניאל כהן: יעד אישי: ביטחון עצמי, יעד מקצועי: מומחה פייתון"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/webhook/telegram", json=payload_update)

    assert res1.status_code == 200
    contract = task_repo.get_mentorship_contract(soldier_id=soldier.id, year=2026)
    assert contract is not None
    assert contract["personal_goal"] == "ביטחון עצמי"
    assert contract["professional_goal"] == "מומחה פייתון"

    assert len(spy_adapter.sent_messages) == 1
    _, reply1 = spy_adapter.sent_messages[0]
    assert "חוזה חניכה" in reply1
    assert "דניאל כהן" in reply1
    assert "ביטחון עצמי" in reply1
    assert "מומחה פייתון" in reply1

    # 2. Query mentorship contract via chat
    payload_query = {
        "update_id": 10016,
        "message": {
            "message_id": 95,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "הצג חוזה חניכה דניאל כהן"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post("/webhook/telegram", json=payload_query)

    assert res2.status_code == 200
    assert len(spy_adapter.sent_messages) == 2
    _, reply2 = spy_adapter.sent_messages[1]
    assert "חוזה חניכה" in reply2
    assert "דניאל כהן" in reply2
    assert "ביטחון עצמי" in reply2
    assert "מומחה פייתון" in reply2
