"""Bulk seeding script for soldiers and teams from CSV."""
import csv
from typing import Optional
from ramad_assistant.db.models import Soldier, Team
from ramad_assistant.db.repository import TaskRepository


def seed_soldiers_from_csv(csv_path: str, repo: TaskRepository) -> int:
    seeded_count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    header_idx = 0
    for idx, line in enumerate(lines[:10]):
        if "שם החייל" in line or "full_name" in line:
            header_idx = idx
            break

    csv_data = "\n".join(lines[header_idx:])
    reader = csv.DictReader(csv_data.splitlines())

    service_type_map = {
        "חובה": "MANDATORY",
        "קבע": "CAREER",
        "מילואים": "RESERVE",
        "יועץ": "CONSULTANT",
        "אזרח": "CONSULTANT",
    }

    for row in reader:
        # Full name
        full_name = (row.get("שם החייל") or row.get("full_name") or "").strip()
        if not full_name:
            continue

        # Team
        team_name = (row.get("צוות") or row.get("team_name") or "").strip()
        team_id: Optional[int] = None
        if team_name:
            team = repo.get_team_by_name(team_name)
            if not team:
                team = repo.create_team(Team(name=team_name))
            team_id = team.id

        # Service type
        raw_service = (row.get("סוג אוכלוסייה") or row.get("service_type") or "MANDATORY").strip()
        service_type = service_type_map.get(raw_service, raw_service)

        # Fields
        rank = (row.get("דרגה") or row.get("rank") or "").strip() or None
        tash_status = (row.get("התאמות ת״ש / מעמד מיוחד") or row.get("tash_status") or "").strip() or None
        current_naat = (row.get("נע\"ת") or row.get("current_naat") or "").strip() or None
        release_date = (row.get("תאריך שחרור/סיום") or row.get("release_date") or "").strip() or None
        academic_status = (row.get("סטטוס תואר") or row.get("academic_status") or "").strip() or None
        education = (row.get("מוסד ותחום לימוד") or row.get("education") or "").strip() or None
        excellence_status = (row.get("סטטוס הצטיינות והוקרה") or row.get("excellence_status") or "").strip() or None
        excellence_notes = (row.get("מועד טקס / הערות הצטיינות") or row.get("excellence_notes") or "").strip() or None
        commander_notes = (row.get("הערות") or row.get("commander_notes") or "").strip() or None

        soldier = Soldier(
            full_name=full_name,
            team_id=team_id,
            service_type=service_type,
            rank=rank,
            tash_status=tash_status,
            academic_status=academic_status,
            excellence_status=excellence_status,
            excellence_notes=excellence_notes,
            release_date=release_date,
            current_naat=current_naat,
            education=education,
            commander_notes=commander_notes,
        )
        soldier = repo.create_soldier(soldier)
        seeded_count += 1

        # Mentorship contract & 1-on-1 meeting date
        p_goal = (row.get("יעד אישי") or row.get("personal_goal") or "").strip()
        prof_goal = (row.get("יעד מקצועי") or row.get("professional_goal") or "").strip()
        last_date = (row.get("תאריך מפגש סטטוס אחרון") or row.get("last_one_on_one_date") or "").strip()

        if soldier.id and (p_goal or prof_goal):
            repo.set_mentorship_goals(
                soldier_id=soldier.id,
                personal_goal=p_goal or "טרם הוגדר",
                professional_goal=prof_goal or "טרם הוגדר",
            )

        if soldier.id and last_date:
            repo.record_one_on_one_meeting(
                soldier_id=soldier.id,
                meeting_date=last_date,
                notes=row.get("הערות") or row.get("notes") or "שיחת חניכה שנתית",
            )

    return seeded_count
