"""Task & Tagab Agent logic with Conversational LLM Tool Calling."""
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from ramad_assistant.core.datetime_utils import get_israel_now
from ramad_assistant.db.models import PersonalTask
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.llm_client import LLMClient

TASK_SYSTEM_INSTRUCTION = """אתה 'סוכן משימות ותג"בים' (Task Agent) של הרמ"ד (ראש מדור טכנולוגי-מודיעיני).
תפקידך לסייע לרמ"ד לנהל ביד רמה את המשימות האישיות שלו, התג"בים (תאריכי גמר ביצוע), וסדרי העדיפויות המבצעיים.

כללי הברזל של הרמ"ד במשימות:
1. עמידה בתג"ב היא קודש.
2. חובת רישום סיבה: לא ניתן לדחות תג"ב ללא ציון סיבה ברורה. אם המשתמש מבקש לדחות משימה ולא ציין סיבה, בקש ממנו בנימוס ובאופן שיחתי לציין את סיבת הדחייה.
3. סדר עדיפויות מובהק (LOW, MEDIUM, HIGH, CRITICAL). ברירת המחדל היא MEDIUM.

הנחיות לשיחה:
- ענה תמיד בעברית טבעית, חופשית, עניינית וזורמת (כמו בשיחה אישית מול ChatGPT או Gemini), ללא תבניות רובוטיות מקובעות.
- השתמש בכלים (Functions) לביצוע פעולות על המשימות (יצירה, מחיקה, סיום, דחייה, רשימה).
- לאחר קבלת נתונים מהכלי, ענה מיד למשתמש בצורה שיחתית, ישירה ואינטליגנטית.
- אם רשימת המשימות ריקה, ענה בטבעיות ובחיוך שהלוח נקי ושאין כרגע משימות פתוחות, והצע לפתוח משימה במידת הצורך. אל תנסה להפעיל כלים נוספים.
- שמור על אמינות ודיוק מוחלטים: הסתמך אך ורק על המידע שחזר מהכלים ללא המצאת משימות או תאריכים שלא קיימים.
"""


class TaskAgent:
    def __init__(self, task_repo: TaskRepository, api_key: Optional[str] = None):
        self.task_repo = task_repo
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.llm = LLMClient(api_key=self.api_key) if self.api_key else None

    async def handle_message(self, text: str, history: Optional[list[dict[str, Any]]] = None) -> str:
        if self.llm:
            tools = [
                {
                    "name": "create_task",
                    "description": "פתיחת משימה חדשה לרמ\"ד עם תג\"ב (תאריך יעד) ורמת עדיפות",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "כותרת או תיאור המשימה"},
                            "tagab_description": {"type": "STRING", "description": "מועד התג\"ב (למשל: מחר בצהריים, היום בערב, 2026-10-15)"},
                            "priority": {"type": "STRING", "description": "עדיפות: LOW, MEDIUM, HIGH, CRITICAL"}
                        },
                        "required": ["title"],
                    },
                },
                {
                    "name": "complete_task",
                    "description": "סימון משימה מסוימת כבוצעה (DONE) לפי מזהה #ID או לפי שם/תיאור",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "task_id": {"type": "INTEGER", "description": "מזהה המשימה (אם ידוע)"},
                            "title_query": {"type": "STRING", "description": "מילות חיפוש בכותרת המשימה"}
                        },
                    },
                },
                {
                    "name": "complete_all_tasks",
                    "description": "סימון כל המשימות הפתוחות כבוצעו (DONE)",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
                {
                    "name": "delete_task",
                    "description": "מחיקה פיזית (Hard delete) של משימה מסוימת מהמערכת לפי מזהה #ID או שם",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "task_id": {"type": "INTEGER", "description": "מזהה המשימה (אם ידוע)"},
                            "title_query": {"type": "STRING", "description": "מילות חיפוש בכותרת המשימה"}
                        },
                    },
                },
                {
                    "name": "delete_all_tasks",
                    "description": "מחיקה פיזית מוחלטת של כל המשימות הפתוחות מהמערכת",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
                {
                    "name": "postpone_task",
                    "description": "דחיית תג\"ב של משימה למועד חדש (חובה לציין סיבה!)",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "reason": {"type": "STRING", "description": "סיבת הדחייה (חובה)"},
                            "task_id": {"type": "INTEGER", "description": "מזהה המשימה"},
                            "title_query": {"type": "STRING", "description": "מילות חיפוש בכותרת המשימה"},
                            "new_date_description": {"type": "STRING", "description": "המועד החדש (למשל: מחר בערב, שבוע הבא)"}
                        },
                        "required": ["reason"],
                    },
                },
                {
                    "name": "list_tasks",
                    "description": "הצגת רשימת המשימות הפתוחות (או בסטטוס אחר)",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "status": {"type": "STRING", "description": "OPEN, DONE, CANCELLED או ריק לכל הפתוחות"}
                        },
                    },
                },
                {
                    "name": "get_daily_briefing",
                    "description": "קבלת דוח בוקר יומי לרמ\"ד (תג\"בים בחריגה, תג\"בים להיום, תג\"בים קריטיים וחריגות 1-על-1)",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
            ]

            async def tool_executor(name: str, args: dict[str, Any]) -> Any:
                if name == "create_task":
                    tagab_text = args.get("tagab_description", "מחר")
                    tagab_dt = self._resolve_date(tagab_text)
                    priority = (args.get("priority") or "MEDIUM").upper()
                    if priority not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                        priority = "MEDIUM"
                    task = PersonalTask(
                        title=args["title"],
                        tagab_at=tagab_dt.strftime("%Y-%m-%d %H:%M"),
                        priority=priority,
                        status="OPEN",
                    )
                    saved = self.task_repo.create_task(task)
                    return {"status": "created", "task": {"id": saved.id, "title": saved.title, "tagab_at": saved.tagab_at, "priority": saved.priority}}

                elif name == "complete_task":
                    task_id = args.get("task_id")
                    query = args.get("title_query")
                    if task_id:
                        updated = self.task_repo.update_task_status(task_id, "DONE")
                        if updated:
                            return {"status": "completed", "task": {"id": updated.id, "title": updated.title}}
                        return {"error": f"משימה #{task_id} לא נמצאה"}
                    if query:
                        matches = self.task_repo.find_tasks_by_query(query, status="OPEN")
                        if len(matches) == 1:
                            t = self.task_repo.update_task_status(matches[0].id, "DONE")
                            return {"status": "completed", "task": {"id": t.id, "title": t.title}}
                        elif len(matches) > 1:
                            return {"multiple_matches": [{"id": m.id, "title": m.title} for m in matches]}
                        return {"error": f"לא נמצאה משימה פתוחה התואמת ל-'{query}'"}
                    return {"error": "נא לציין מספר משימה או מילות חיפוש"}

                elif name == "complete_all_tasks":
                    count = self.task_repo.complete_all_tasks()
                    return {"status": "all_completed", "count": count}

                elif name == "delete_task":
                    task_id = args.get("task_id")
                    query = args.get("title_query")
                    if task_id:
                        t = self.task_repo.get_task(task_id)
                        if not t:
                            return {"error": f"משימה #{task_id} לא נמצאה"}
                        self.task_repo.delete_task(task_id)
                        return {"status": "deleted", "task": {"id": t.id, "title": t.title}}
                    if query:
                        matches = self.task_repo.find_tasks_by_query(query, status="OPEN")
                        if len(matches) == 1:
                            t = matches[0]
                            self.task_repo.delete_task(t.id)
                            return {"status": "deleted", "task": {"id": t.id, "title": t.title}}
                        elif len(matches) > 1:
                            return {"multiple_matches": [{"id": m.id, "title": m.title} for m in matches]}
                        return {"error": f"לא נמצאה משימה פתוחה התואמת ל-'{query}'"}
                    return {"error": "נא לציין מספר משימה או מילות חיפוש"}

                elif name == "delete_all_tasks":
                    count = self.task_repo.delete_all_tasks(status="OPEN")
                    return {"status": "all_deleted", "count": count}

                elif name == "postpone_task":
                    reason = args.get("reason", "").strip()
                    if not reason:
                        return {"error": "חובת רישום סיבה לדחיית תג\"ב"}
                    new_date_text = args.get("new_date_description", "מחר")
                    new_dt = self._resolve_date(new_date_text)
                    new_dt_str = new_dt.strftime("%Y-%m-%d %H:%M")

                    target_task: Optional[PersonalTask] = None
                    if args.get("task_id"):
                        target_task = self.task_repo.get_task(args["task_id"])
                    elif args.get("title_query"):
                        matches = self.task_repo.find_tasks_by_query(args["title_query"], status="OPEN")
                        if len(matches) == 1:
                            target_task = matches[0]
                        elif len(matches) > 1:
                            return {"multiple_matches": [{"id": m.id, "title": m.title} for m in matches]}

                    if not target_task:
                        return {"error": "משימה לא נמצאה"}

                    updated = self.task_repo.postpone_task(target_task.id, new_dt_str, reason)
                    return {"status": "postponed", "task": {"id": updated.id, "title": updated.title, "new_tagab": updated.tagab_at, "postpone_count": updated.postpone_count}}

                elif name == "list_tasks":
                    st = args.get("status") or "OPEN"
                    tasks = self.task_repo.list_tasks(status=st)
                    if not tasks:
                        return {
                            "tasks": [],
                            "message": "אין כרגע משימות פתוחות ברשימה. ענה למשתמש שהלוח נקי ושאין כרגע משימות פתוחות, והצע לפתוח משימה חדשה במידת הצורך."
                        }
                    return {"tasks": [{"id": t.id, "title": t.title, "tagab_at": t.tagab_at, "priority": t.priority, "status": t.status} for t in tasks]}

                elif name == "get_daily_briefing":
                    return {"briefing": self.build_daily_briefing()}

                return {"error": f"Unknown tool: {name}"}

            return await self.llm.chat(
                system_instruction=TASK_SYSTEM_INSTRUCTION,
                user_message=text,
                history=history,
                tools=tools,
                tool_executor=tool_executor,
            )

        return self._fallback_handle_message(text)

    def _fallback_handle_message(self, text: str) -> str:
        # 1. Bulk complete commands ("סיימתי את כל המשימות", "השלמתי את כל המשימות")
        if re.search(r"(?:סיימתי|השלמתי|סגור|בוצעו)\s+את\s+כל\s+המשימות", text) or any(
            phrase in text for phrase in ["סיימתי את כל המשימות", "השלמתי את כל המשימות", "סגור את כל המשימות"]
        ):
            count = self.task_repo.complete_all_tasks()
            if count == 0:
                return "📋 אין כרגע משימות פתוחות לסימון כבוצעו."
            return f"✅ כל המשימות הפתוחות ({count}) סומנו כבוצעו בהצלחה!"

        # 2. Bulk delete commands ("תמחק את כל המשימות", "מחק את כל המשימות")
        if re.search(r"(?:תמחק|מחק|למחוק)\s+את\s+כל\s+המשימות", text) or any(
            phrase in text for phrase in ["תמחק את כל המשימות", "מחק את כל המשימות", "למחוק את כל המשימות"]
        ):
            count = self.task_repo.delete_all_tasks(status="OPEN")
            if count == 0:
                return "📋 אין כרגע משימות פתוחות למחיקה."
            return f"🗑️ כל המשימות הפתוחות ({count}) נמחקו לצמיתות מהמערכת."

        # 3. Check for single task hard deletion commands ("תמחק", "מחק", "למחוק", "delete")
        if any(w in text for w in ["תמחק", "מחק", "למחוק", "delete"]):
            task, error_msg = self._resolve_task_or_prompt(
                text,
                action_words=["תמחק", "מחק", "למחוק", "delete", "בבקשה"],
                action_label="למחיקה",
            )
            if error_msg:
                return error_msg
            assert task is not None
            self.task_repo.delete_task(task.id)
            return f"🗑️ משימה #{task.id} ('{task.title}') נמחקה לצמיתות."

        # 4. Check for postpone commands
        if any(w in text for w in ["תדחה", "דחה", "דחיית תג\"ב", "דחה תג\"ב", "postpone"]):
            return self._handle_postpone(text)

        # 5. Check for single complete/done commands
        if any(w in text for w in ["סיימתי", "בוצעה", "השלמתי", "סגור משימה", "סגור את המשימה", "done"]):
            task, error_msg = self._resolve_task_or_prompt(
                text,
                action_words=["סיימתי", "בוצעה", "השלמתי", "סגור משימה", "סגור את המשימה", "done", "בבקשה"],
                action_label="לסימון כבוצעה",
            )
            if error_msg:
                return error_msg
            assert task is not None
            self.task_repo.update_task_status(task.id, "DONE")
            return f"✅ משימה #{task.id} ('{task.title}') סומנה כבוצעה."

        # 6. Check for single cancel commands
        if any(w in text for w in ["בטל", "ביטול", "cancel"]):
            task, error_msg = self._resolve_task_or_prompt(
                text,
                action_words=["בטל", "ביטול", "cancel", "בבקשה"],
                action_label="לביטול",
            )
            if error_msg:
                return error_msg
            assert task is not None
            self.task_repo.update_task_status(task.id, "CANCELLED")
            return f"🗑️ משימה #{task.id} ('{task.title}') בוטלה."

        # 7. Check for list commands
        if any(w in text for w in ["מה המשימות", "הצג משימות", "רשימת משימות", "משימות שלי", "משימות פתוחות", "list tasks"]):
            return self.format_tasks_list(status="OPEN")

        # 8. Check explicit task creation intent
        is_create_intent = any(
            k in text for k in [
                "תפתח משימה", "צור משימה", "משימה חדשה", "תוסיף משימה",
                "רשום משימה", "תזכורת", "לתג\"ב", "תגב", "משימה:", "משימה ל"
            ]
        ) or text.strip().startswith("משימה ")

        if is_create_intent:
            _, reply = self.parse_and_create_task(text)
            return reply

        # Guardrail against creating arbitrary text as task
        return (
            "⚠️ לא זיהיתי את הפקודה המבוקשת למשימה.\n"
            "• לפתיחת משימה: 'תפתח משימה לתג\"ב מחר: <כותרת>'\n"
            "• למחיקה: 'תמחק משימה #1' או 'תמחק את כל המשימות'\n"
            "• לסיום: 'סיימתי משימה #1' או 'סיימתי את כל המשימות'\n"
            "• לצפייה: 'מה המשימות הפתוחות'"
        )

    def _extract_target(self, text: str, action_words: list[str]) -> tuple[Optional[int], str]:
        """Extracts (task_id, query_str) from command text."""
        id_match = re.search(r"(?:משימה\s*(?:#|מספר\s*)?|#)(\d+)", text)
        if id_match:
            return int(id_match.group(1)), ""

        clean = text
        for w in action_words:
            clean = re.sub(w, "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"[\?\.\!\:\,]", "", clean).strip()
        clean = re.sub(r"^(?:את\s+)?(?:ה?משימה\s+)?(?:של\s+|על\s+)?", "", clean).strip()
        clean = re.sub(r"^(?:את\s+)", "", clean).strip()
        return None, clean

    def _resolve_task_or_prompt(
        self, text: str, action_words: list[str], action_label: str
    ) -> tuple[Optional[PersonalTask], Optional[str]]:
        """
        Resolves a task either by ID or query text.
        Returns (task, None) if exactly one task found.
        Returns (None, error_or_clarification_message) if 0 or multiple tasks found.
        """
        task_id, query = self._extract_target(text, action_words)
        if task_id is not None:
            task = self.task_repo.get_task(task_id)
            if not task:
                return None, f"⚠️ לא נמצאה משימה עם מזהה #{task_id}."
            return task, None

        if not query:
            return None, f"⚠️ נא ציין מספר משימה או כותרת {action_label} (לדוגמה: '#1' או שם המשימה)."

        matches = self.task_repo.find_tasks_by_query(query, status="OPEN")
        if not matches:
            return None, f"⚠️ לא נמצאה משימה פתוחה התואמת ל-'{query}'."

        if len(matches) == 1:
            return matches[0], None

        lines = [f"⚠️ נמצאו {len(matches)} משימות תואמות ל-'{query}'. נא ציין את מספר המזהה המדויק {action_label}:"]
        for t in matches:
            lines.append(f"• [#{t.id}] *{t.title}* (תג\"ב: {t.tagab_at})")
        return None, "\n".join(lines)

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

        overdue_mentorships = self.task_repo.get_overdue_mentorships(max_days=30)
        if overdue_mentorships:
            sections.append(f"👥 *חיילים בחריגת שיחת 1-על-1 (> 30 יום)* ({len(overdue_mentorships)}):")
            for m in overdue_mentorships:
                last_d = m.get("last_one_on_one_date") or "טרם בוצעה"
                sections.append(f"• *{m['full_name']}* (שיחה אחרונה: {last_d})")
            sections.append("")

        if not overdue and not today_tasks and not critical_48h and not overdue_mentorships:
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
        now = get_israel_now()
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
