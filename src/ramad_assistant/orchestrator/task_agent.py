"""Task & Tagab Agent logic."""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository


class TaskAgent:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo

    def handle_message(self, text: str) -> str:
        # 1. Check for complete/done commands
        if any(w in text for w in ["סיימתי", "בוצעה", "השלמתי", "סגור משימה", "done"]):
            match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
            if match:
                task_id = int(match.group(1))
                task = self.task_repo.update_task_status(task_id, "DONE")
                if task:
                    return f"✅ משימה #{task_id} ('{task.title}') סומנה כבוצעה."
                return f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."

        # 2. Check for cancel commands
        if any(w in text for w in ["בטל", "מחק משימה", "cancel"]):
            match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
            if match:
                task_id = int(match.group(1))
                task = self.task_repo.update_task_status(task_id, "CANCELLED")
                if task:
                    return f"🗑️ משימה #{task_id} ('{task.title}') בוטלה."
                return f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."

        # 3. Check for list commands
        if any(w in text for w in ["מה המשימות", "הצג משימות", "רשימת משימות", "משימות שלי", "משימות פתוחות", "list tasks"]):
            return self.format_tasks_list(status="OPEN")

        # 4. Fallback to parse and create task
        _, reply = self.parse_and_create_task(text)
        return reply

    def format_tasks_list(self, status: Optional[str] = "OPEN") -> str:
        tasks = self.task_repo.list_tasks(status=status)
        if not tasks:
            return "📋 אין כרגע משימות פתוחות."

        lines = [f"📋 *משימות פתוחות* ({len(tasks)}):"]
        for t in tasks:
            lines.append(
                f"• [#{t.id}] *{t.title}* | תג\"ב: {t.tagab_at} | עדיפות: {t.priority}"
            )
        return "\n".join(lines)

    def parse_and_create_task(self, text: str) -> tuple[PersonalTask, str]:
        now = datetime.now(timezone.utc)
        tagab_dt = now + timedelta(days=1)  # Default: tomorrow

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

        priority = "MEDIUM"
        if "דחוף" in text or "קריטי" in lower_text or "critical" in lower_text:
            priority = "CRITICAL"
        elif "גבוה" in text or "high" in lower_text:
            priority = "HIGH"
        elif "נמוך" in text or "low" in lower_text:
            priority = "LOW"

        cleaned_title = text
        if ":" in text:
            cleaned_title = text.split(":", 1)[1].strip()
        else:
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
