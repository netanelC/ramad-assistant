"""Comprehensive tests for Mobile REST API (v1)."""
import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.db.models import PersonalTask, Soldier, Team
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.gateway.app import create_app


@pytest.fixture
def repo(tmp_path) -> TaskRepository:
    db_file = tmp_path / "test_api.db"
    r = TaskRepository(str(db_file))
    r.init_db()

    # Seed initial test teams
    t1 = r.create_team(Team(name="טטריס", team_lead_name="אביהוא"))
    t2 = r.create_team(Team(name="קסבה", team_lead_name="זיו"))

    # Seed soldiers
    r.create_soldier(
        Soldier(
            full_name="ישראל ישראלי",
            team_id=t1.id,
            service_type="MANDATORY",
            rank="סמ\"ר",
            release_date="2026-11-01",
            current_naat="אחראי ציוד",
        )
    )
    r.create_soldier(
        Soldier(
            full_name="דנה לוי",
            team_id=t2.id,
            service_type="CAREER",
            rank="סגן",
            release_date="2028-01-01",
            current_naat="אחראית הדרכה",
            excellence_status="מצטיינת מדור",
        )
    )

    # Seed tasks
    r.create_task(
        PersonalTask(
            title="משימה דחופה בחריגה",
            tagab_at="2026-10-01 10:00",
            priority="CRITICAL",
            status="OPEN",
        )
    )
    r.create_task(
        PersonalTask(
            title="משימה עתידית",
            tagab_at="2026-12-31 18:00",
            priority="LOW",
            status="OPEN",
        )
    )

    return r


@pytest.fixture
def app(repo: TaskRepository):
    return create_app(task_repo=repo)


@pytest.mark.asyncio
async def test_teams_endpoints(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List teams
        res = await client.get("/api/v1/teams")
        assert res.status_code == 200
        teams = res.json()
        assert len(teams) == 2
        names = [t["name"] for t in teams]
        assert "טטריס" in names
        assert "קסבה" in names

        # 2. Section summary
        res_sum = await client.get("/api/v1/teams/summary")
        assert res_sum.status_code == 200
        data = res_sum.json()
        assert data["total_teams"] == 2
        assert data["total_soldiers"] == 2


@pytest.mark.asyncio
async def test_soldiers_crud_and_actions(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List soldiers
        res = await client.get("/api/v1/soldiers")
        assert res.status_code == 200
        soldiers = res.json()
        assert len(soldiers) == 2

        # 2. Filter by service_type
        res_mand = await client.get("/api/v1/soldiers?service_type=MANDATORY")
        assert len(res_mand.json()) == 1
        assert res_mand.json()[0]["full_name"] == "ישראל ישראלי"

        # 3. Create a new soldier
        new_soldier_payload = {
            "full_name": "יוסי כהן",
            "service_type": "MANDATORY",
            "rank": "רב\"ט",
            "release_date": "2027-04-15",
            "current_naat": "אחראי הוואי",
        }
        res_create = await client.post("/api/v1/soldiers", json=new_soldier_payload)
        assert res_create.status_code == 201
        created = res_create.json()
        soldier_id = created["id"]
        assert created["full_name"] == "יוסי כהן"

        # 4. Get by ID
        res_get = await client.get(f"/api/v1/soldiers/{soldier_id}")
        assert res_get.status_code == 200
        assert res_get.json()["rank"] == "רב\"ט"

        # 5. Update soldier
        res_update = await client.put(f"/api/v1/soldiers/{soldier_id}", json={"rank": "סמ\"ר"})
        assert res_update.status_code == 200
        assert res_update.json()["rank"] == "סמ\"ר"

        # 6. Record 1-on-1 meeting
        res_meeting = await client.post(
            f"/api/v1/soldiers/{soldier_id}/one-on-one",
            json={"notes": "שיחת חתך אישית חיובית מאוד"},
        )
        assert res_meeting.status_code == 200
        assert res_meeting.json()["status"] == "recorded"

        # 7. Assign new Naat
        res_naat = await client.post(
            f"/api/v1/soldiers/{soldier_id}/naat",
            json={"duty_name": "אחראי למידה ומקצועיות"},
        )
        assert res_naat.status_code == 200
        assert res_naat.json()["status"] == "assigned"

        # 8. Check Naat history
        res_naat_hist = await client.get(f"/api/v1/soldiers/{soldier_id}/naat-history")
        assert res_naat_hist.status_code == 200
        history = res_naat_hist.json()
        assert len(history) >= 2

        # 9. Set mentorship contract
        res_mentor = await client.put(
            f"/api/v1/soldiers/{soldier_id}/mentorship",
            json={
                "personal_goal": "פיתוח ביטחון עצמי בדיונים",
                "professional_goal": "הובלת פרויקט ארכיטקטוני",
            },
        )
        assert res_mentor.status_code == 200
        assert res_mentor.json()["contract"]["personal_goal"] == "פיתוח ביטחון עצמי בדיונים"

        # 10. Delete soldier
        res_del = await client.delete(f"/api/v1/soldiers/{soldier_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_tasks_crud_and_postpone(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List open tasks
        res = await client.get("/api/v1/tasks")
        assert res.status_code == 200
        tasks = res.json()
        assert len(tasks) == 2

        # 2. Filter by overdue
        res_overdue = await client.get("/api/v1/tasks?urgency=overdue")
        assert res_overdue.status_code == 200
        overdue_tasks = res_overdue.json()
        assert len(overdue_tasks) == 1
        assert overdue_tasks[0]["title"] == "משימה דחופה בחריגה"
        overdue_id = overdue_tasks[0]["id"]

        # 3. Postpone task requires reason!
        res_bad_postpone = await client.post(
            f"/api/v1/tasks/{overdue_id}/postpone",
            json={"reason": " ", "new_tagab_at": "2026-11-01 10:00"},
        )
        assert res_bad_postpone.status_code == 422 or res_bad_postpone.status_code == 400

        # Valid postpone with reason
        res_ok_postpone = await client.post(
            f"/api/v1/tasks/{overdue_id}/postpone",
            json={"reason": "המתנה לאישור תקציב מרס\"ן", "new_tagab_at": "2026-11-01 10:00"},
        )
        assert res_ok_postpone.status_code == 200
        postponed = res_ok_postpone.json()
        assert postponed["postpone_count"] == 1
        assert postponed["last_postpone_reason"] == "המתנה לאישור תקציב מרס\"ן"

        # 4. Create new task
        res_create = await client.post(
            "/api/v1/tasks",
            json={
                "title": "הכנת מצגת מדורית",
                "tagab_at": "2026-10-25 14:00",
                "priority": "HIGH",
            },
        )
        assert res_create.status_code == 201
        new_task_id = res_create.json()["id"]

        # 5. Mark task as DONE
        res_done = await client.put(
            f"/api/v1/tasks/{new_task_id}/status",
            json={"status": "DONE"},
        )
        assert res_done.status_code == 200
        assert res_done.json()["status"] == "DONE"

        # 6. Complete all open tasks
        res_comp_all = await client.post("/api/v1/tasks/complete-all")
        assert res_comp_all.status_code == 200
        assert res_comp_all.json()["count"] >= 1

        # Check that open tasks list is now empty
        res_empty = await client.get("/api/v1/tasks?status=OPEN")
        assert len(res_empty.json()) == 0


@pytest.mark.asyncio
async def test_notifications_endpoints(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register device token
        res = await client.post(
            "/api/v1/notifications/register-token",
            json={"fcm_token": "fcm_test_device_token_12345", "device_name": "Pixel 8 Pro"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "registered"

        # Check status
        res_status = await client.get("/api/v1/notifications/status")
        assert res_status.status_code == 200
        assert res_status.json()["registered_devices_count"] >= 1


@pytest.mark.asyncio
async def test_agent_chat_and_action_cards(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test briefing endpoint
        res_brief = await client.get("/api/v1/agent/briefing")
        assert res_brief.status_code == 200
        assert "briefing" in res_brief.json()

        # Test chat endpoint with task command
        res_chat = await client.post(
            "/api/v1/agent/chat",
            json={"text": "תפתח משימה לתאם שיחה עם איתי למחר בבוקר בעדיפות גבוהה"},
        )
        assert res_chat.status_code == 200
        body = res_chat.json()
        assert "response_text" in body
        assert len(body["response_text"]) > 0
        assert "action_cards" in body
        # Action card was detected for the created task
        assert len(body["action_cards"]) >= 1
        assert body["action_cards"][0]["card_type"] == "task"
        assert body["action_cards"][0]["deeplink_tab"] == "tasks"
