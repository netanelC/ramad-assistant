"""Task & Tagab Agent logic."""
import re
from datetime import datetime, timedelta, timezone
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


class TaskAgent:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo

    def parse_and_create_task(self, text: str) -> tuple[PersonalTask, str]:
        now = datetime.now(timezone.utc)
        tagab_dt = now + timedelta(days=1)  # Default: tomorrow

        # Simple semantic time resolution
        lower_text = text.lower()
        if "מחר בצהריים" in text or "מחר 12:00" in text:
            tagab_dt = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        elif "מחר בערב" in text:
            tagab_dt = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0)
        elif "מחר" in text:
            tagab_dt = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        elif "היום בערב" in text:
            tagab_dt = now.replace(hour=18, minute=0, second=0)
        elif "היום" in text:
            tagab_dt = now.replace(hour=16, minute=0, second=0)

        # Priority resolution
        priority = "MEDIUM"
        if "דחוף" in text or "קריטי" in lower_text or "critical" in lower_text:
            priority = "CRITICAL"
        elif "גבוה" in text or "high" in lower_text:
            priority = "HIGH"
        elif "נמוך" in text or "low" in lower_text:
            priority = "LOW"

        # Title extraction: extract what comes after colon, or clean command prefixes
        cleaned_title = text
        if ":" in text:
            cleaned_title = text.split(":", 1)[1].strip()
        else:
            # Remove command keywords
            cleaned_title = re.sub(
                r"^(תפתח משימה|צור משימה|משימה חדשה|תזכורת)(\s+לתג\"ב\s+[^\:]+)?",
                "",
                text,
            ).strip()

        if not cleaned_title:
            cleaned_title = text

        task = PersonalTask(
            title=cleaned_title,
            tagab_at=tagab_dt.strftime("%Y-%m-%d %H:%M"),
            priority=priority,
            status="OPEN",
        )
        saved_task = self.task_repo.create_task(task)

        reply = (
            f"✅ *נפתחה משימה חדשה* (מזהה #{saved_task.id})\n"
            f"• *כותרת*: {saved_task.title}\n"
            f"• *תג\"ב*: {saved_task.tagab_at}\n"
            f"• *עדיפות*: {saved_task.priority}"
        )
        return saved_task, reply
