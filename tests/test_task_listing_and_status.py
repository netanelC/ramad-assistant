import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


@pytest.mark.asyncio
async def test_list_open_tasks_via_chat(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    task_repo.create_task(
        PersonalTask(
            title="בדיקת מוכנות צוות 1",
            tagab_at="2026-10-15 12:00",
            priority="HIGH",
            status="OPEN",
        )
    )

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "מה המשימות הפתוחות שלי?", "user_id": "999888"},
        )

    assert response.status_code == 200
    reply_text = response.json()["response_text"]
    assert "משימות פתוחות" in reply_text
    assert "בדיקת מוכנות צוות 1" in reply_text
    assert "HIGH" in reply_text


@pytest.mark.asyncio
async def test_mark_task_as_done_via_chat(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    saved_task = task_repo.create_task(
        PersonalTask(
            title="להכין סיכום שבועי לרע\"ן",
            tagab_at="2026-10-12 10:00",
            priority="MEDIUM",
            status="OPEN",
        )
    )

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": f"סיימתי משימה #{saved_task.id}", "user_id": "999888"},
        )

    assert response.status_code == 200
    task_after = task_repo.get_task(saved_task.id)
    assert task_after.status == "DONE"

    reply_text = response.json()["response_text"]
    assert "בוצעה" in reply_text


@pytest.mark.asyncio
async def test_complete_all_tasks_via_chat(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    task_repo.create_task(PersonalTask(title="משימה א", tagab_at="2026-10-15 12:00", priority="HIGH", status="OPEN"))
    task_repo.create_task(PersonalTask(title="משימה ב", tagab_at="2026-10-15 14:00", priority="LOW", status="OPEN"))

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "סיימתי את כל המשימות", "user_id": "999888"},
        )

    assert response.status_code == 200
    open_tasks = task_repo.list_tasks(status="OPEN")
    assert len(open_tasks) == 0

    done_tasks = task_repo.list_tasks(status="DONE")
    assert len(done_tasks) == 2

    reply_text = response.json()["response_text"]
    assert "סומנו כבוצעו" in reply_text
    assert "2" in reply_text


@pytest.mark.asyncio
async def test_delete_all_tasks_via_chat(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    task_repo.create_task(PersonalTask(title="משימה א", tagab_at="2026-10-15 12:00", priority="HIGH", status="OPEN"))
    task_repo.create_task(PersonalTask(title="משימה ב", tagab_at="2026-10-15 14:00", priority="LOW", status="OPEN"))

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "תמחק את כל המשימות", "user_id": "999888"},
        )

    assert response.status_code == 200
    all_tasks = task_repo.list_tasks()
    assert len(all_tasks) == 0

    reply_text = response.json()["response_text"]
    assert "נמחקו לצמיתות" in reply_text
    assert "2" in reply_text


@pytest.mark.asyncio
async def test_delete_single_task_by_title_query(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    t1 = task_repo.create_task(PersonalTask(title="שיחה דחופה עם טל שבו", tagab_at="2026-10-15 12:00", priority="HIGH", status="OPEN"))
    t2 = task_repo.create_task(PersonalTask(title="מצגת לרע\"ן", tagab_at="2026-10-15 14:00", priority="LOW", status="OPEN"))

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "תמחק את המשימה של השיחה עם טל", "user_id": "999888"},
        )

    assert response.status_code == 200
    assert task_repo.get_task(t1.id) is None
    assert task_repo.get_task(t2.id) is not None

    reply_text = response.json()["response_text"]
    assert "נמחקה לצמיתות" in reply_text
    assert "שיחה דחופה עם טל שבו" in reply_text


@pytest.mark.asyncio
async def test_delete_non_existent_task_does_not_create_task(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    app = create_app(task_repo=task_repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"text": "תמחק את המשימה של שחרור דני", "user_id": "999888"},
        )

    assert response.status_code == 200
    all_tasks = task_repo.list_tasks()
    assert len(all_tasks) == 0

    reply_text = response.json()["response_text"]
    assert "לא נמצאה משימה פתוחה" in reply_text
