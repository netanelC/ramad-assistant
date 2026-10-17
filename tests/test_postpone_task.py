import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


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

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": f"תדחה משימה #{saved_task.id} למחר בערב בגלל בלת\"ם מבצעי", "user_id": "999888"},
        )

    assert response.status_code == 200
    task_after = task_repo.get_task(saved_task.id)
    assert task_after.postpone_count == 1
    assert task_after.last_postpone_reason == "בלת\"ם מבצעי"
    assert task_after.status == "POSTPONED"

    reply_text = response.json()["response_text"]
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

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": f"תדחה משימה #{saved_task.id} למחר בערב", "user_id": "999888"},
        )

    assert response.status_code == 200
    task_after = task_repo.get_task(saved_task.id)
    assert task_after.postpone_count == 0  # Not postponed!

    reply_text = response.json()["response_text"]
    assert "סיבה" in reply_text
