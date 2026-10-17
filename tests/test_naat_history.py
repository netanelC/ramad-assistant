import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.models import Soldier
from ramad_assistant.db.repository import TaskRepository


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

    app = create_app(task_repo=task_repo)

    # 1. Assign new na'at via chat
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "שבץ נע\"ת לאורי לוי: אחראי הדרכה", "user_id": "999888"},
        )

    assert res1.status_code == 200
    soldier_after = task_repo.get_soldier(soldier.id)
    assert soldier_after.current_naat == "אחראי הדרכה"

    # Verify history in DB
    history = task_repo.get_naat_history(soldier.id)
    assert len(history) >= 2  # old and new
    assert any(h["duty_name"] == "קשר מדורי" and h["end_date"] is not None for h in history)
    assert any(h["duty_name"] == "אחראי הדרכה" and h["end_date"] is None for h in history)

    # 2. Query na'at history via chat
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "היסטוריית נע\"ת אורי לוי", "user_id": "999888"},
        )

    assert res2.status_code == 200
    reply_history = res2.json()["response_text"]
    assert "היסטוריית נע\"ת" in reply_history
    assert "אורי לוי" in reply_history
    assert "קשר מדורי" in reply_history
    assert "אחראי הדרכה" in reply_history
