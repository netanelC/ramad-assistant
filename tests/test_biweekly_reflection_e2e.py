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
async def test_full_biweekly_self_debrief_state_machine_e2e(tmp_path):
    """
    Verifies complete Issue #19 acceptance criteria:
    1. POST /cron/biweekly-reflection initiates Question 1 in reflection thread.
    2. Multi-turn state machine waits for user response, reflects, and presents next question.
    3. Questions strictly follow doctrine:
       - (1) אוטומט
       - (2) נחישות ומקצועיות
       - (3) אנשים
    4. Final turn extracts 2 points to preserve and 2 to improve into reflection_logs.
    5. Database persistence verified.
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
        # 1. Trigger bi-weekly reflection via Cron
        init_res = await client.post("/cron/biweekly-reflection", headers=headers)
        assert init_res.status_code == 200
        assert len(spy_adapter.sent_messages) == 1
        _, prompt_q1 = spy_adapter.sent_messages[-1]
        assert "שגרת תחקור עצמי דו-שבועי" in prompt_q1
        assert "שאלה 1 מתוך 3: האם נשאבתי לאוטומט?" in prompt_q1

        # 2. Answer Question 1 (אוטומט)
        ans1_payload = {
            "update_id": 10030,
            "message": {
                "message_id": 130,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560000,
                "text": "שמרתי על ימי היציאה למשפחה, אבל נשאבתי לישיבות ולא הספקתי לעשות סיבוב יומי במדור."
            }
        }
        res_q1 = await client.post("/webhook/telegram", json=ans1_payload)
        assert res_q1.status_code == 200
        assert len(spy_adapter.sent_messages) == 2
        _, prompt_q2 = spy_adapter.sent_messages[-1]
        assert "שיקוף שאלה 1 נרשם" in prompt_q2
        assert "שאלה 2 מתוך 3: האם הייתי האדם הכי נחוש בחדר ושמרתי על מקצועיות?" in prompt_q2

        # 3. Answer Question 2 (נחישות ומקצועיות)
        ans2_payload = {
            "update_id": 10031,
            "message": {
                "message_id": 131,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560020,
                "text": "הפגנתי קור רוח מול הצוותים, אבל נכנס מעקף טכנולוגי שלא הכנסתי מיד לג'ירה."
            }
        }
        res_q2 = await client.post("/webhook/telegram", json=ans2_payload)
        assert res_q2.status_code == 200
        assert len(spy_adapter.sent_messages) == 3
        _, prompt_q3 = spy_adapter.sent_messages[-1]
        assert "שיקוף שאלה 2 נרשם" in prompt_q3
        assert "שאלה 3 מתוך 3: האם ראיתי את האנשים שלי?" in prompt_q3

        # 4. Answer Question 3 (אנשים)
        ans3_payload = {
            "update_id": 10032,
            "message": {
                "message_id": 132,
                "from": {"id": 999888, "first_name": "Ramad"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1728560040,
                "text": "עשיתי שיחות 1-על-1 לרוב החיילים ונתתי פידבק דוגרי, אך פספסתי חייל אחד מעל 30 יום."
            }
        }
        res_q3 = await client.post("/webhook/telegram", json=ans3_payload)
        assert res_q3.status_code == 200
        assert len(spy_adapter.sent_messages) == 4
        _, summary_msg = spy_adapter.sent_messages[-1]

        # Verify summary output strictly contains 2 preserve and 2 improve
        assert "סיכום תחקור עצמי דו-שבועי" in summary_msg
        assert "2 נקודות לשימור" in summary_msg
        assert "2 נקודות לשיפור" in summary_msg

    # 5. Verify database persistence in reflection_logs
    logs = task_repo.get_reflection_logs()
    assert len(logs) == 1
    log = logs[0]
    assert "נשאבתי לישיבות" in log["q1_automation_answer"]
    assert "מעקף טכנולוגי" in log["q2_resolve_answer"]
    assert "פספסתי חייל אחד" in log["q3_people_answer"]
    assert len(log["points_to_preserve"]) == 2
    assert len(log["points_to_improve"]) == 2
