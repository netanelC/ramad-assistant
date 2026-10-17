import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore
from ramad_assistant.db.seed_doctrine import seed_doctrine


@pytest.mark.asyncio
async def test_mentor_agent_socratic_consultation_e2e(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    # Seed doctrine
    await seed_doctrine(doctrine_path="doctrine.md", db_url=f"sqlite:///{db_path}")

    vector_store = DoctrineVectorStore(repo=task_repo)

    app = create_app(task_repo=task_repo)
    # Ensure app orchestrator uses the populated vector store
    app.state.orchestrator.vector_store = vector_store
    app.state.orchestrator.mentor_agent.vector_store = vector_store

    # Section head expresses dilemma regarding calendar load & burnout
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/agent/chat",
            json={
                "text": "מראה פיקודית: אני מרגיש עומס מטורף ושאני טובע בדיונים ובניהול הלו\"ז",
                "user_id": "999888",
            },
        )

    assert res.status_code == 200
    reply = res.json()["response_text"]
    assert "מראה פיקודית" in reply
    assert "מה שלא ביומן – לא קורה" in reply or "יומן" in reply
    assert "שאלה למחשבה" in reply
