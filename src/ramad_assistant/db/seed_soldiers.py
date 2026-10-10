"""Bulk seeding script for soldiers and teams from CSV."""
import csv
from typing import Optional
from ramad_assistant.db.models import Soldier, Team
from ramad_assistant.db.repository import TaskRepository


def seed_soldiers_from_csv(csv_path: str, repo: TaskRepository) -> int:
    seeded_count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = (row.get("team_name") or "").strip()
            team_id: Optional[int] = None
            if team_name:
                team = repo.get_team_by_name(team_name)
                if not team:
                    team = repo.create_team(Team(name=team_name))
                team_id = team.id

            soldier = Soldier(
                full_name=row["full_name"].strip(),
                team_id=team_id,
                service_type=(row.get("service_type") or "MANDATORY").strip(),
                release_date=row.get("release_date") or None,
                current_naat=row.get("current_naat") or None,
                education=row.get("education") or None,
                commander_notes=row.get("commander_notes") or None,
            )
            repo.create_soldier(soldier)
            seeded_count += 1

    return seeded_count
