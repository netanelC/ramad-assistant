import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository


@pytest.mark.asyncio
async def test_natural_language_task_creation_e2e(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "תפתח משימה לתג\"ב מחר בצהריים: לבדוק ביצועים מול צוות 1", "user_id": "999888"},
        )

    assert response.status_code == 200
    body = response.json()
    reply_text = body["response_text"]

    # Verify task was saved in the database
    tasks = task_repo.list_tasks(status="OPEN")
    assert len(tasks) == 1
    task = tasks[0]
    assert "לבדוק ביצועים מול צוות 1" in task.title
    assert task.tagab_at is not None
    assert task.status == "OPEN"

    # Verify confirmation sent back in response
    assert "נפתחה משימה" in reply_text or "פתחתי" in reply_text or "נוצרה" in reply_text
    assert "תג\"ב" in reply_text
