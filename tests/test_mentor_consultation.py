import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore
from ramad_assistant.db.seed_doctrine import seed_doctrine


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_mentor_agent_socratic_consultation_e2e(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    # Seed doctrine
    await seed_doctrine(doctrine_path="doctrine.md", db_url=f"sqlite:///{db_path}")

    vector_store = DoctrineVectorStore(repo=task_repo)

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )
    # Ensure app orchestrator uses the populated vector store
    app.state.orchestrator.vector_store = vector_store
    app.state.orchestrator.mentor_agent.vector_store = vector_store

    # Section head expresses dilemma regarding calendar load & burnout
    payload = {
        "update_id": 10020,
        "message": {
            "message_id": 110,
            "from": {"id": 999888, "first_name": "Ramad"},
            "chat": {"id": 999888, "type": "private"},
            "date": 1728560000,
            "text": "מראה פיקודית: אני מרגיש עומס מטורף ושאני טובע בדיונים ובניהול הלו\"ז"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/webhook/telegram", json=payload)

    assert res.status_code == 200
    assert len(spy_adapter.sent_messages) == 1
    recipient_id, reply = spy_adapter.sent_messages[0]
    assert recipient_id == "999888"
    assert "מראה פיקודית" in reply
    assert "מה שלא ביומן – לא קורה" in reply or "יומן" in reply
    assert "שאלה למחשבה" in reply
