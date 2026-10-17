import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.models import Soldier
from ramad_assistant.db.repository import TaskRepository


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

    app = create_app(task_repo=task_repo)

    # 1. Update mentorship contract goals via chat
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/api/v1/agent/chat",
            json={
                "text": "עדכן חוזה חניכה לדניאל כהן: יעד אישי: ביטחון עצמי, יעד מקצועי: מומחה פייתון",
                "user_id": "999888",
            },
        )

    assert res1.status_code == 200
    contract = task_repo.get_mentorship_contract(soldier_id=soldier.id, year=2026)
    assert contract is not None
    assert contract["personal_goal"] == "ביטחון עצמי"
    assert contract["professional_goal"] == "מומחה פייתון"

    reply1 = res1.json()["response_text"]
    assert "חוזה חניכה" in reply1
    assert "דניאל כהן" in reply1
    assert "ביטחון עצמי" in reply1
    assert "מומחה פייתון" in reply1

    # 2. Query mentorship contract via chat
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "הצג חוזה חניכה דניאל כהן", "user_id": "999888"},
        )

    assert res2.status_code == 200
    reply2 = res2.json()["response_text"]
    assert "חוזה חניכה" in reply2
    assert "דניאל כהן" in reply2
    assert "ביטחון עצמי" in reply2
    assert "מומחה פייתון" in reply2
