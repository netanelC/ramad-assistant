import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.seed_soldiers import seed_soldiers_from_csv


@pytest.mark.asyncio
async def test_seed_soldiers_from_csv_and_query_profile(tmp_path):
    db_path = str(tmp_path / "test_tasks.db")
    task_repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    task_repo.init_db()

    csv_content = """full_name,team_name,service_type,release_date,current_naat,personal_goal,professional_goal,last_one_on_one_date
ישראל ישראלי,צוות 1,MANDATORY,2027-04-15,אחראי הוואי מדורי,ביטחון עצמי,ענן מתקדם,2026-09-15
דניאל כהן,צוות 2,RESERVE,,חונך מקצועי,איזון מילואים,הובלת מודול,2026-09-20
"""
    csv_file = tmp_path / "soldiers_test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Run seed script
    seed_count = seed_soldiers_from_csv(str(csv_file), task_repo)
    assert seed_count == 2

    app = create_app(task_repo=task_repo)

    # 1. Query individual soldier profile
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "פרופיל חייל ישראל ישראלי", "user_id": "999888"},
        )

    assert res1.status_code == 200
    reply1 = res1.json()["response_text"]
    assert "ישראל ישראלי" in reply1
    assert "צוות 1" in reply1
    assert "MANDATORY" in reply1
    assert "אחראי הוואי מדורי" in reply1

    # 2. Query team soldiers list
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post(
            "/api/v1/agent/chat",
            json={"text": "מי החיילים בצוות 1?", "user_id": "999888"},
        )

    assert res2.status_code == 200
    reply2 = res2.json()["response_text"]
    assert "חיילי צוות 1" in reply2
    assert "ישראל ישראלי" in reply2
