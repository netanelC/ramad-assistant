import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.seed_soldiers import seed_soldiers_from_csv


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_seed_soldiers_from_csv_and_query_profile(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    csv_content = """full_name,team_name,service_type,release_date,current_naat,personal_goal,professional_goal,last_one_on_one_date
ישראל ישראלי,צוות 1,MANDATORY,2027-04-15,אחראי הוואי מדורי,ביטחון עצמי,ענן מתקדם,2026-09-15
דניאל כהן,צוות 2,RESERVE,,חונך מקצועי,איזון מילואים,הובלת מודול,2026-09-20
"""
    csv_file = tmp_path / "soldiers_test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Run seed script
    seed_count = seed_soldiers_from_csv(str(csv_file), task_repo)
    assert seed_count == 2

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    # 1. Query individual soldier profile
    payload_profile = {
        "update_id": 10009,
        "message": {
            "message_id": 80,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "פרופיל חייל ישראל ישראלי"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/webhook/telegram", json=payload_profile)

    assert res1.status_code == 200
    assert len(spy_adapter.sent_messages) == 1
    _, reply1 = spy_adapter.sent_messages[0]
    assert "ישראל ישראלי" in reply1
    assert "צוות 1" in reply1
    assert "MANDATORY" in reply1
    assert "אחראי הוואי מדורי" in reply1

    # 2. Query team soldiers list
    payload_team = {
        "update_id": 10010,
        "message": {
            "message_id": 81,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "מי החיילים בצוות 1?"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post("/webhook/telegram", json=payload_team)

    assert res2.status_code == 200
    assert len(spy_adapter.sent_messages) == 2
    _, reply2 = spy_adapter.sent_messages[1]
    assert "חיילי צוות 1" in reply2
    assert "ישראל ישראלי" in reply2
