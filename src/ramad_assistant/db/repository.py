"""Repository layer for tasks, teams, soldiers, and naat history."""
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional
from ramad_assistant.db.models import PersonalTask, Team, Soldier


class TaskRepository:
    def __init__(self, db_url: str = "sqlite:///./ramad_tasks.db"):
        self.db_path = db_url.replace("sqlite:///", "")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
            # 1. Teams table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    team_lead_name TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # 2. Soldiers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS soldiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    team_id INTEGER,
                    service_type TEXT NOT NULL,
                    release_date TEXT,
                    current_naat TEXT,
                    education TEXT,
                    commander_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
                )
            """)

            # 3. Naat History table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS naat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    soldier_id INTEGER NOT NULL,
                    duty_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    notes TEXT,
                    FOREIGN KEY (soldier_id) REFERENCES soldiers(id) ON DELETE CASCADE
                )
            """)

            # 4. Personal Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personal_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    details TEXT,
                    tagab_at TEXT NOT NULL,
                    priority TEXT DEFAULT 'MEDIUM',
                    status TEXT DEFAULT 'OPEN',
                    related_team_id INTEGER,
                    related_soldier_id INTEGER,
                    postpone_count INTEGER DEFAULT 0,
                    last_postpone_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    # --- Teams Methods ---
    def create_team(self, team: Team) -> Team:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO teams (name, team_lead_name, description, created_at) VALUES (?, ?, ?, ?)",
                (team.name, team.team_lead_name, team.description, now),
            )
            conn.commit()
            team.id = cursor.lastrowid
            team.created_at = now
            return team

    def get_team_by_name(self, name: str) -> Optional[Team]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM teams WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            return Team(
                id=row["id"],
                name=row["name"],
                team_lead_name=row["team_lead_name"],
                description=row["description"],
                created_at=row["created_at"],
            )

    def get_team(self, team_id: int) -> Optional[Team]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
            if not row:
                return None
            return Team(
                id=row["id"],
                name=row["name"],
                team_lead_name=row["team_lead_name"],
                description=row["description"],
                created_at=row["created_at"],
            )

    # --- Soldiers Methods ---
    def create_soldier(self, soldier: Soldier) -> Soldier:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO soldiers (
                    full_name, team_id, service_type, release_date,
                    current_naat, education, commander_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    soldier.full_name,
                    soldier.team_id,
                    soldier.service_type,
                    soldier.release_date,
                    soldier.current_naat,
                    soldier.education,
                    soldier.commander_notes,
                    now,
                    now,
                ),
            )
            soldier.id = cursor.lastrowid
            soldier.created_at = now
            soldier.updated_at = now

            # If created with initial na'at, record in history
            if soldier.current_naat:
                conn.execute(
                    """
                    INSERT INTO naat_history (soldier_id, duty_name, start_date, end_date, notes)
                    VALUES (?, ?, ?, NULL, 'Initial assignment')
                    """,
                    (soldier.id, soldier.current_naat, now[:10]),
                )

            conn.commit()
            return soldier

    def get_soldier(self, soldier_id: int) -> Optional[Soldier]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM soldiers WHERE id = ?", (soldier_id,)).fetchone()
            if not row:
                return None
            return Soldier(
                id=row["id"],
                full_name=row["full_name"],
                team_id=row["team_id"],
                service_type=row["service_type"],
                release_date=row["release_date"],
                current_naat=row["current_naat"],
                education=row["education"],
                commander_notes=row["commander_notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_soldier_by_name(self, full_name: str) -> Optional[Soldier]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM soldiers WHERE full_name LIKE ?",
                (f"%{full_name}%",),
            ).fetchone()
            if not row:
                return None
            return Soldier(
                id=row["id"],
                full_name=row["full_name"],
                team_id=row["team_id"],
                service_type=row["service_type"],
                release_date=row["release_date"],
                current_naat=row["current_naat"],
                education=row["education"],
                commander_notes=row["commander_notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_soldiers(self, team_id: Optional[int] = None) -> list[Soldier]:
        query = "SELECT * FROM soldiers"
        params: list[int] = []
        if team_id is not None:
            query += " WHERE team_id = ?"
            params.append(team_id)
        query += " ORDER BY full_name ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                Soldier(
                    id=row["id"],
                    full_name=row["full_name"],
                    team_id=row["team_id"],
                    service_type=row["service_type"],
                    release_date=row["release_date"],
                    current_naat=row["current_naat"],
                    education=row["education"],
                    commander_notes=row["commander_notes"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    # --- Na'at History Methods ---
    def assign_naat(self, soldier_id: int, duty_name: str, start_date: Optional[str] = None) -> bool:
        date_str = start_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # 1. Close current active duty in naat_history
            conn.execute(
                "UPDATE naat_history SET end_date = ? WHERE soldier_id = ? AND end_date IS NULL",
                (date_str, soldier_id),
            )
            # 2. Insert new duty in naat_history
            conn.execute(
                """
                INSERT INTO naat_history (soldier_id, duty_name, start_date, end_date)
                VALUES (?, ?, ?, NULL)
                """,
                (soldier_id, duty_name, date_str),
            )
            # 3. Update current_naat on soldier
            conn.execute(
                "UPDATE soldiers SET current_naat = ?, updated_at = ? WHERE id = ?",
                (duty_name, now, soldier_id),
            )
            conn.commit()
            return True

    def get_naat_history(self, soldier_id: int) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM naat_history WHERE soldier_id = ? ORDER BY start_date ASC",
                (soldier_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Personal Tasks Methods ---
    def create_task(self, task: PersonalTask) -> PersonalTask:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO personal_tasks (
                    title, details, tagab_at, priority, status,
                    related_team_id, related_soldier_id, postpone_count,
                    last_postpone_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.title,
                    task.details,
                    task.tagab_at,
                    task.priority,
                    task.status,
                    task.related_team_id,
                    task.related_soldier_id,
                    task.postpone_count,
                    task.last_postpone_reason,
                    now,
                    now,
                ),
            )
            conn.commit()
            task.id = cursor.lastrowid
            task.created_at = now
            task.updated_at = now
            return task

    def list_tasks(self, status: Optional[str] = None) -> list[PersonalTask]:
        query = "SELECT * FROM personal_tasks"
        params: list[str] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY tagab_at ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                PersonalTask(
                    id=row["id"],
                    title=row["title"],
                    details=row["details"],
                    tagab_at=row["tagab_at"],
                    priority=row["priority"],
                    status=row["status"],
                    related_team_id=row["related_team_id"],
                    related_soldier_id=row["related_soldier_id"],
                    postpone_count=row["postpone_count"],
                    last_postpone_reason=row["last_postpone_reason"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_task(self, task_id: int) -> Optional[PersonalTask]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM personal_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return PersonalTask(
                id=row["id"],
                title=row["title"],
                details=row["details"],
                tagab_at=row["tagab_at"],
                priority=row["priority"],
                status=row["status"],
                related_team_id=row["related_team_id"],
                related_soldier_id=row["related_soldier_id"],
                postpone_count=row["postpone_count"],
                last_postpone_reason=row["last_postpone_reason"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def update_task_status(self, task_id: int, status: str) -> Optional[PersonalTask]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE personal_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def postpone_task(
        self, task_id: int, new_tagab_at: str, reason: str
    ) -> Optional[PersonalTask]:
        task = self.get_task(task_id)
        if not task:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE personal_tasks
                SET tagab_at = ?, postpone_count = postpone_count + 1,
                    last_postpone_reason = ?, status = 'POSTPONED', updated_at = ?
                WHERE id = ?
                """,
                (new_tagab_at, reason, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)
