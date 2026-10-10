"""Repository layer for personal tasks."""
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from ramad_assistant.db.models import PersonalTask


class TaskRepository:
    def __init__(self, db_url: str = "sqlite:///./ramad_tasks.db"):
        self.db_path = db_url.replace("sqlite:///", "")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
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
