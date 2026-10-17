import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository


@pytest.mark.asyncio
async def test_multiturn_conversational_memory(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Message 1: General greeting / architecture query
        res1 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "היי, איך המערכת הזאת בנויה?", "user_id": "999888"},
        )
        assert res1.status_code == 200

        # Message 2: Follow-up question
        res2 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "איזה סוכנים יש לך?", "user_id": "999888"},
        )
        assert res2.status_code == 200

    # Verify orchestrator maintains conversation history for user
    orchestrator = app.state.orchestrator
    history = orchestrator.user_histories.get("999888", [])
    assert len(history) == 4  # 2 user messages + 2 model replies
    assert history[0]["text"] == "היי, איך המערכת הזאת בנויה?"
    assert history[2]["text"] == "איזה סוכנים יש לך?"
