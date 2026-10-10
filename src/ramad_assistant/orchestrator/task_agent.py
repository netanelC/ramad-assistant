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
        # 1. Check for postpone commands
        if any(w in text for w in ["תדחה", "דחה", "דחיית תג\"ב", "דחה תג\"ב", "postpone"]):
            return self._handle_postpone(text)

        # 2. Check for complete/done commands
        if any(w in text for w in ["סיימתי", "בוצעה", "השלמתי", "סגור משימה", "done"]):
            match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
            if match:
                task_id = int(match.group(1))
                task = self.task_repo.update_task_status(task_id, "DONE")
                if task:
                    return f"✅ משימה #{task_id} ('{task.title}') סומנה כבוצעה."
                return f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."

        # 3. Check for cancel commands
        if any(w in text for w in ["בטל", "מחק משימה", "cancel"]):
            match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
            if match:
                task_id = int(match.group(1))
                task = self.task_repo.update_task_status(task_id, "CANCELLED")
                if task:
                    return f"🗑️ משימה #{task_id} ('{task.title}') בוטלה."
                return f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."

        # 4. Check for list commands
        if any(w in text for w in ["מה המשימות", "הצג משימות", "רשימת משימות", "משימות שלי", "משימות פתוחות", "list tasks"]):
            return self.format_tasks_list(status="OPEN")

        # 5. Fallback to parse and create task
        _, reply = self.parse_and_create_task(text)
        return reply

    def build_daily_briefing(self) -> str:
        tasks = self.task_repo.list_tasks(status="OPEN")
        now = datetime.now(timezone.utc)
        today_date_str = now.strftime("%Y-%m-%d")

        overdue: list[PersonalTask] = []
        today_tasks: list[PersonalTask] = []
        critical_48h: list[PersonalTask] = []

        for t in tasks:
            task_date_str = t.tagab_at[:10]
            if task_date_str < today_date_str:
                overdue.append(t)
            elif task_date_str == today_date_str:
                today_tasks.append(t)
            else:
                if t.priority == "CRITICAL":
                    critical_48h.append(t)

        sections: list[str] = ["🌅 *דוח בוקר יומי לרמ\"ד*\n"]

        if overdue:
            sections.append(f"🚨 *תג\"בים בחריגה (Overdue)* ({len(overdue)}):")
            for t in overdue:
                sections.append(f"• [#{t.id}] *{t.title}* (פג תוקף: {t.tagab_at})")
            sections.append("")

        if today_tasks:
            sections.append(f"📋 *תג\"בים להיום* ({len(today_tasks)}):")
            for t in today_tasks:
                sections.append(f"• [#{t.id}] *{t.title}* ({t.tagab_at})")
            sections.append("")

        if critical_48h:
            sections.append(f"⏳ *תג\"בים קריטיים ל-48 השעות הקרובות* ({len(critical_48h)}):")
            for t in critical_48h:
                sections.append(f"• [#{t.id}] *{t.title}* ({t.tagab_at})")
            sections.append("")

        if not overdue and not today_tasks and not critical_48h:
            sections.append("✨ אין תג\"בים דחופים או חורגים להיום. יום פורה ומוצלח!")

        return "\n".join(sections).strip()

    def _handle_postpone(self, text: str) -> str:
        match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
        if not match:
            return "⚠️ נא ציין את מזהה המשימה שברצונך לדחות (לדוגמה: 'תדחה משימה #1')."

        task_id = int(match.group(1))
        task = self.task_repo.get_task(task_id)
        if not task:
            return f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."

        reason_match = re.search(r"(?:בגלל|עקב|בשל|מסיבת|סיבה:)\s*(.+)$", text)
        if not reason_match:
            return "⚠️ *חובת רישום סיבה*: לא ניתן לדחות תג\"ב ללא ציון סיבה (קו אדום פיקודי). נא ציין את סיבת הדחייה (לדוגמה: 'בגלל בלת\"ם מבצעי')."

        reason = reason_match.group(1).strip()
        new_tagab_dt = self._resolve_date(text)
        new_tagab_str = new_tagab_dt.strftime("%Y-%m-%d %H:%M")

        updated_task = self.task_repo.postpone_task(
            task_id=task_id,
            new_tagab_at=new_tagab_str,
            reason=reason,
        )
        if not updated_task:
            return f"⚠️ שגיאה בעדכון משימה #{task_id}."

        return (
            f"⏳ *משימה #{task_id} נדחתה* לתאריך {updated_task.tagab_at} (דחייה מספר {updated_task.postpone_count}).\n"
            f"• *סיבה*: {updated_task.last_postpone_reason}"
        )

    def _resolve_date(self, text: str) -> datetime:
        now = datetime.now(timezone.utc)
        if "מחר בערב" in text:
            return (now + timedelta(days=1)).replace(hour=18, minute=0, second=0)
        elif "מחר בצהריים" in text or "מחר 12:00" in text:
            return (now + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        elif "מחר" in text:
            return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        elif "היום בערב" in text:
            return now.replace(hour=18, minute=0, second=0)
        elif "היום" in text:
            return now.replace(hour=16, minute=0, second=0)
        return now + timedelta(days=1)

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
        tagab_dt = self._resolve_date(text)
        lower_text = text.lower()

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
