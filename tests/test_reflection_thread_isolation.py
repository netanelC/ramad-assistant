import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository


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

    app = create_app(task_repo=task_repo)

    headers = {"X-API-Secret": "dev-secret"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Trigger bi-weekly reflection via cron
        init_res = await client.post("/cron/biweekly-reflection", headers=headers)
        assert init_res.status_code == 200
        prompt_q1 = init_res.json()["prompt"]
        assert "שאלה 1 מתוך 3: האם נשאבתי לאוטומט?" in prompt_q1

        # Step 2: Interleaved operational command (create a task)
        res_task = await client.post(
            "/api/v1/agent/chat",
            json={
                "text": "תפתח משימה לתג\"ב מחר בצהריים: בדיקת עמדות קצה",
                "user_id": "app_user",
            },
        )
        assert res_task.status_code == 200
        reply_task = res_task.json()["response_text"]
        assert "נפתחה משימה חדשה" in reply_task or "פתחתי" in reply_task or "נוצרה" in reply_task

        # Step 3: Verify operational task was persisted in DB
        tasks = task_repo.list_tasks(status="OPEN")
        assert len(tasks) == 1
        assert "בדיקת עמדות קצה" in tasks[0].title

        # Step 4: Resume reflection by answering Question 1
        res_ans1 = await client.post(
            "/api/v1/agent/chat",
            json={
                "text": "הקפדתי על יציאה מוקדמת בימי שלישי, אבל בקושי עשיתי סיבוב במדור בגלל דיונים",
                "user_id": "app_user",
            },
        )
        assert res_ans1.status_code == 200
        reply_ans1 = res_ans1.json()["response_text"]
        # Should now present Question 2
        assert "שאלה 2 מתוך 3: האם הייתי האדם הכי נחוש בחדר" in reply_ans1
