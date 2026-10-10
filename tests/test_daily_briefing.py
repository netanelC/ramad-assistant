from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_cron_daily_briefing_requires_api_secret(tmp_path):
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
        # Without secret header
        response = await client.post("/cron/daily-briefing")
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_cron_daily_briefing_formats_and_dispatches_digest(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d 10:00")
    today = now.strftime("%Y-%m-%d 14:00")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d 16:00")

    # 1. Overdue task
    task_repo.create_task(
        PersonalTask(
            title="מעקב אינטגרציה מעבדה",
            tagab_at=yesterday,
            priority="HIGH",
            status="OPEN",
        )
    )
    # 2. Today task
    task_repo.create_task(
        PersonalTask(
            title="סנכרון רש\"צים שבועי",
            tagab_at=today,
            priority="MEDIUM",
            status="OPEN",
        )
    )
    # 3. Critical in 48h
    task_repo.create_task(
        PersonalTask(
            title="הכנת דמו לסגן מפקד היחידה",
            tagab_at=tomorrow,
            priority="CRITICAL",
            status="OPEN",
        )
    )
    # 4. Completed task (should NOT appear)
    task_repo.create_task(
        PersonalTask(
            title="משימה שכבר הסתיימה",
            tagab_at=yesterday,
            priority="LOW",
            status="DONE",
        )
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    headers = {"X-API-Secret": "dev-secret"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/cron/daily-briefing", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "briefing_sent"}

    assert len(spy_adapter.sent_messages) == 1
    recipient_id, briefing_text = spy_adapter.sent_messages[0]
    assert recipient_id == "999888"
    assert "דוח בוקר יומי" in briefing_text
    assert "מעקב אינטגרציה מעבדה" in briefing_text
    assert "סנכרון רש\"צים שבועי" in briefing_text
    assert "משימה שכבר הסתיימה" not in briefing_text


@pytest.mark.asyncio
async def test_cron_daily_briefing_includes_overdue_mentorships(tmp_path):
    from ramad_assistant.db.models import Soldier

    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    # Soldier 1: Has overdue meeting (> 30 days)
    s1 = task_repo.create_soldier(
        Soldier(full_name="דניאל כהן", service_type="MANDATORY")
    )
    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d")
    task_repo.record_one_on_one_meeting(soldier_id=s1.id, meeting_date=old_date, notes="שיחה ישנה")

    # Soldier 2: Recent meeting (10 days ago, NOT overdue)
    s2 = task_repo.create_soldier(
        Soldier(full_name="יובל אברהם", service_type="PERMANENT")
    )
    recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    task_repo.record_one_on_one_meeting(soldier_id=s2.id, meeting_date=recent_date, notes="שיחה עדכנית")

    # Soldier 3: Never had a meeting (overdue / missing)
    task_repo.create_soldier(
        Soldier(full_name="נועם שחר", service_type="MANDATORY")
    )

    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"],
        task_repo=task_repo,
    )

    headers = {"X-API-Secret": "dev-secret"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/cron/daily-briefing", headers=headers)

    assert response.status_code == 200
    assert len(spy_adapter.sent_messages) == 1
    _, briefing_text = spy_adapter.sent_messages[0]

    assert "חריגת שיחת 1-על-1" in briefing_text
    assert "דניאל כהן" in briefing_text
    assert "נועם שחר" in briefing_text
    assert "יובל אברהם" not in briefing_text

