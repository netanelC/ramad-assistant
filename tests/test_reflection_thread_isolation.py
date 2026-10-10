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
async def test_reflection_thread_isolation_and_interleaved_command(tmp_path):
    """
    Verifies ADR-0002 thread isolation:
    1. Reflection initiated in thread_reflection_{date}.
    2. User sends operational command (task creation) interleaved.
    3. Operational command routes to thread_user_{user_id} without corrupting reflection state.
    4. User responds to reflection question, continuing reflection turn.
    """
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    headers = {"X-API-Secret": "dev-secret"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Trigger bi-weekly reflection via cron
        init_res = await client.post("/cron/biweekly-reflection", headers=headers)
        assert init_res.status_code == 200
        assert len(spy_adapter.sent_messages) == 1
        assert "שאלה 1 מתוך 3: האם נשאבתי לאוטומט?" in spy_adapter.sent_messages[-1][1]

        # Step 2: Interleaved operational command (create a task)
        task_msg = {
            "update_id": 10025,
            "message": {
                "message_id": 121,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560000,
                "text": "תפתח משימה לתג\"ב מחר בצהריים: בדיקת עמדות קצה"
            }
        }
        res_task = await client.post("/webhook/telegram", json=task_msg)
        assert res_task.status_code == 200
        assert len(spy_adapter.sent_messages) == 2
        assert "נפתחה משימה חדשה" in spy_adapter.sent_messages[-1][1]

        # Step 3: Verify operational task was persisted in DB
        tasks = task_repo.list_tasks(status="OPEN")
        assert len(tasks) == 1
        assert "בדיקת עמדות קצה" in tasks[0].title

        # Step 4: Resume reflection by answering Question 1
        ans1_msg = {
            "update_id": 10026,
            "message": {
                "message_id": 122,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560010,
                "text": "הקפדתי על יציאה מוקדמת בימי שלישי, אבל בקושי עשיתי סיבוב במדור בגלל דיונים"
            }
        }
        res_ans1 = await client.post("/webhook/telegram", json=ans1_msg)
        assert res_ans1.status_code == 200
        assert len(spy_adapter.sent_messages) == 3
        # Should now present Question 2
        assert "שאלה 2 מתוך 3: האם הייתי האדם הכי נחוש בחדר" in spy_adapter.sent_messages[-1][1]
