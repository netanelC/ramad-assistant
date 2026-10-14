"""Repository layer for tasks, teams, soldiers, naat history, and mentorship contracts."""
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from ramad_assistant.db.models import PersonalTask, Team, Soldier, ReflectionLog


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
                    rank TEXT,
                    tash_status TEXT,
                    academic_status TEXT,
                    excellence_status TEXT,
                    excellence_notes TEXT,
                    release_date TEXT,
                    current_naat TEXT,
                    education TEXT,
                    commander_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
                )
            """)

            # Run safe migrations for existing SQLite databases
            soldier_columns = [col[1] for col in conn.execute("PRAGMA table_info(soldiers)").fetchall()]
            for new_col in ["rank", "tash_status", "academic_status", "excellence_status", "excellence_notes"]:
                if new_col not in soldier_columns:
                    conn.execute(f"ALTER TABLE soldiers ADD COLUMN {new_col} TEXT")

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

            # 4. Mentorship Contracts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mentorship_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    soldier_id INTEGER NOT NULL,
                    contract_year INTEGER NOT NULL,
                    personal_goal TEXT NOT NULL,
                    professional_goal TEXT NOT NULL,
                    last_one_on_one_date TEXT,
                    next_one_on_one_due TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (soldier_id, contract_year),
                    FOREIGN KEY (soldier_id) REFERENCES soldiers(id) ON DELETE CASCADE
                )
            """)

            # 5. Personal Tasks table
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

            # 6. Reflection Logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT NOT NULL,
                    q1_automation_answer TEXT,
                    q2_resolve_answer TEXT,
                    q3_people_answer TEXT,
                    points_to_preserve TEXT DEFAULT '[]',
                    points_to_improve TEXT DEFAULT '[]',
                    summary_insights TEXT,
                    created_at TEXT NOT NULL
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
                    full_name, team_id, service_type, rank, tash_status,
                    academic_status, excellence_status, excellence_notes,
                    release_date, current_naat, education, commander_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    soldier.full_name,
                    soldier.team_id,
                    soldier.service_type,
                    soldier.rank,
                    soldier.tash_status,
                    soldier.academic_status,
                    soldier.excellence_status,
                    soldier.excellence_notes,
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

    def _row_to_soldier(self, row: Any) -> Soldier:
        keys = row.keys()
        return Soldier(
            id=row["id"],
            full_name=row["full_name"],
            team_id=row["team_id"],
            service_type=row["service_type"],
            rank=row["rank"] if "rank" in keys else None,
            tash_status=row["tash_status"] if "tash_status" in keys else None,
            academic_status=row["academic_status"] if "academic_status" in keys else None,
            excellence_status=row["excellence_status"] if "excellence_status" in keys else None,
            excellence_notes=row["excellence_notes"] if "excellence_notes" in keys else None,
            release_date=row["release_date"],
            current_naat=row["current_naat"],
            education=row["education"],
            commander_notes=row["commander_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_soldier(self, soldier_id: int) -> Optional[Soldier]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM soldiers WHERE id = ?", (soldier_id,)).fetchone()
            if not row:
                return None
            return self._row_to_soldier(row)

    def get_soldier_by_name(self, full_name: str) -> Optional[Soldier]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM soldiers WHERE full_name LIKE ?",
                (f"%{full_name}%",),
            ).fetchone()
            if not row:
                return None
            return self._row_to_soldier(row)

    def list_soldiers(self, team_id: Optional[int] = None) -> list[Soldier]:
        query = "SELECT * FROM soldiers"
        params: list[int] = []
        if team_id is not None:
            query += " WHERE team_id = ?"
            params.append(team_id)
        query += " ORDER BY full_name ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_soldier(row) for row in rows]

    def get_upcoming_releases(self, days_ahead: int = 90) -> list[Soldier]:
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        limit_str = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        query = """
            SELECT * FROM soldiers
            WHERE release_date IS NOT NULL
              AND release_date >= ?
              AND release_date <= ?
            ORDER BY release_date ASC
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (today_str, limit_str)).fetchall()
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
            conn.execute(
                "UPDATE naat_history SET end_date = ? WHERE soldier_id = ? AND end_date IS NULL",
                (date_str, soldier_id),
            )
            conn.execute(
                """
                INSERT INTO naat_history (soldier_id, duty_name, start_date, end_date)
                VALUES (?, ?, ?, NULL)
                """,
                (soldier_id, duty_name, date_str),
            )
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

    # --- Mentorship Contracts Methods ---
    def set_mentorship_goals(
        self,
        soldier_id: int,
        personal_goal: str,
        professional_goal: str,
        year: int = 2026,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO mentorship_contracts (
                    soldier_id, contract_year, personal_goal, professional_goal,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(soldier_id, contract_year) DO UPDATE SET
                    personal_goal = excluded.personal_goal,
                    professional_goal = excluded.professional_goal,
                    notes = coalesce(excluded.notes, mentorship_contracts.notes),
                    updated_at = excluded.updated_at
                """,
                (soldier_id, year, personal_goal, professional_goal, notes, now, now),
            )
            conn.commit()
        contract = self.get_mentorship_contract(soldier_id, year)
        assert contract is not None
        return contract

    def get_mentorship_contract(self, soldier_id: int, year: int = 2026) -> Optional[dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM mentorship_contracts WHERE soldier_id = ? AND contract_year = ?",
                (soldier_id, year),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def record_one_on_one_meeting(
        self, soldier_id: int, meeting_date: Optional[str] = None, notes: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        date_str = meeting_date or now.strftime("%Y-%m-%d")
        next_due_str = (datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        year = int(date_str[:4])
        iso_now = now.isoformat()

        with self._get_connection() as conn:
            # Update contract if exists, otherwise create basic contract entry
            conn.execute(
                """
                INSERT INTO mentorship_contracts (
                    soldier_id, contract_year, personal_goal, professional_goal,
                    last_one_on_one_date, next_one_on_one_due, notes, created_at, updated_at
                ) VALUES (?, ?, 'טרם הוגדר', 'טרם הוגדר', ?, ?, ?, ?, ?)
                ON CONFLICT(soldier_id, contract_year) DO UPDATE SET
                    last_one_on_one_date = excluded.last_one_on_one_date,
                    next_one_on_one_due = excluded.next_one_on_one_due,
                    notes = case when excluded.notes is not null then excluded.notes else mentorship_contracts.notes end,
                    updated_at = excluded.updated_at
                """,
                (soldier_id, year, date_str, next_due_str, notes, iso_now, iso_now),
            )
            conn.commit()
        return self.get_mentorship_contract(soldier_id, year)

    def get_overdue_mentorships(self, max_days: int = 30) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        threshold_date = (now - timedelta(days=max_days)).strftime("%Y-%m-%d")
        year = now.year

        query = """
            SELECT s.id, s.full_name, s.service_type, t.name as team_name,
                   mc.last_one_on_one_date, mc.next_one_on_one_due
            FROM soldiers s
            LEFT JOIN teams t ON s.team_id = t.id
            LEFT JOIN mentorship_contracts mc ON s.id = mc.soldier_id AND mc.contract_year = ?
            WHERE mc.last_one_on_one_date IS NULL OR mc.last_one_on_one_date < ?
            ORDER BY s.full_name ASC
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (year, threshold_date)).fetchall()
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

    def delete_task(self, task_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM personal_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_all_tasks(self, status: Optional[str] = "OPEN") -> int:
        query = "DELETE FROM personal_tasks"
        params: list[str] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def complete_all_tasks(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE personal_tasks SET status = 'DONE', updated_at = ? WHERE status = 'OPEN'",
                (now,),
            )
            conn.commit()
            return cursor.rowcount

    def find_tasks_by_query(
        self, query: str, status: Optional[str] = "OPEN"
    ) -> list[PersonalTask]:
        tasks = self.list_tasks(status=status)
        clean_q = query.lower().strip()
        if not clean_q:
            return []

        # 1. Exact substring match
        matched = [t for t in tasks if clean_q in t.title.lower() or (t.details and clean_q in t.details.lower())]
        if matched:
            return matched

        # 2. Token overlap with Hebrew normalization
        stopwords = {"את", "של", "על", "עם", "כל", "זה", "זו", "רק", "גם", "או", "אם", "עד", "כי", "לגבי", "בנושא"}
        raw_tokens = [w for w in clean_q.split() if w not in stopwords and len(w) >= 2]
        if not raw_tokens:
            return []

        # Expand tokens: e.g. "השיחה" -> ["השיחה", "שיחה"]
        expanded_tokens: set[str] = set()
        for tok in raw_tokens:
            expanded_tokens.add(tok)
            if tok.startswith("ה") and len(tok) >= 3:
                expanded_tokens.add(tok[1:])

        scored_tasks: list[tuple[int, PersonalTask]] = []
        for t in tasks:
            text_target = f"{t.title} {t.details or ''}".lower()
            target_words = set(text_target.split())
            # Also expand target words without leading 'ה'
            expanded_target_words = set(target_words)
            for tw in target_words:
                if tw.startswith("ה") and len(tw) >= 3:
                    expanded_target_words.add(tw[1:])

            overlap = sum(
                1 for tok in expanded_tokens
                if tok in expanded_target_words or any(tok in tw for tw in target_words)
            )
            if overlap > 0:
                scored_tasks.append((overlap, t))

        if not scored_tasks:
            return []

        # Sort by overlap score descending
        scored_tasks.sort(key=lambda x: x[0], reverse=True)
        max_score = scored_tasks[0][0]
        # Return tasks that achieved max score
        return [t for score, t in scored_tasks if score == max_score]

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

    # --- Reflection Logs Methods ---
    def save_reflection_log(self, log: ReflectionLog) -> ReflectionLog:
        now = datetime.now(timezone.utc).isoformat()
        import json
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reflection_logs (
                    session_date, q1_automation_answer, q2_resolve_answer,
                    q3_people_answer, points_to_preserve, points_to_improve,
                    summary_insights, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.session_date,
                    log.q1_automation_answer,
                    log.q2_resolve_answer,
                    log.q3_people_answer,
                    json.dumps(log.points_to_preserve, ensure_ascii=False),
                    json.dumps(log.points_to_improve, ensure_ascii=False),
                    log.summary_insights,
                    now,
                ),
            )
            conn.commit()
            log.id = cursor.lastrowid
            log.created_at = now
            return log

    def get_reflection_logs(self, limit: int = 10) -> list[dict[str, Any]]:
        import json
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reflection_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["points_to_preserve"] = json.loads(d["points_to_preserve"]) if d.get("points_to_preserve") else []
                d["points_to_improve"] = json.loads(d["points_to_improve"]) if d.get("points_to_improve") else []
                results.append(d)
            return results

