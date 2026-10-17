from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.models import Soldier
from ramad_assistant.db.repository import TaskRepository


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

    app = create_app(task_repo=task_repo)

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    expected_next_due = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/agent/chat",
            json={
                "text": "ביצעתי שיחת 1-על-1 עם דניאל כהן: דיברנו על יעדים אישיים והתקדמות במדור",
                "user_id": "999888",
            },
        )

    assert res.status_code == 200
    contract = task_repo.get_mentorship_contract(soldier_id=soldier.id, year=now.year)
    assert contract is not None
    assert contract["last_one_on_one_date"] == today_str
    assert contract["next_one_on_one_due"] == expected_next_due
    assert "דיברנו על יעדים אישיים" in contract["notes"]

    reply = res.json()["response_text"]
    assert "תועדה שיחת 1-על-1" in reply
    assert "דניאל כהן" in reply
    assert expected_next_due in reply
