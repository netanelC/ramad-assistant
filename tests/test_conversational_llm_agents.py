import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.repository import TaskRepository


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_multiturn_conversational_memory(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Message 1: General greeting / architecture query
        msg1 = {
            "update_id": 10050,
            "message": {
                "message_id": 71,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560000,
                "text": "היי, איך המערכת הזאת בנויה?"
            }
        }
        res1 = await client.post("/webhook/telegram", json=msg1)
        assert res1.status_code == 200
        assert len(spy_adapter.sent_messages) == 1

        # Message 2: Follow-up question
        msg2 = {
            "update_id": 10051,
            "message": {
                "message_id": 72,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560010,
                "text": "איזה סוכנים יש לך?"
            }
        }
        res2 = await client.post("/webhook/telegram", json=msg2)
        assert res2.status_code == 200
        assert len(spy_adapter.sent_messages) == 2

        # Verify orchestrator maintains conversation history for user
        orchestrator = app.state.orchestrator
        history = orchestrator.user_histories.get("999888", [])
        assert len(history) == 4  # 2 user messages + 2 model replies
        assert history[0]["text"] == "היי, איך המערכת הזאת בנויה?"
        assert history[2]["text"] == "איזה סוכנים יש לך?"
