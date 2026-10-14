"""HR & People Agent logic with Conversational LLM Tool Calling."""
import os
import re
from typing import Any, Optional
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.llm_client import LLMClient

HR_SYSTEM_INSTRUCTION = """אתה 'סוכן כוח אדם ופיתוח אנשים' (HR Agent) של מדור טכנולוגי-מודיעיני.
תפקידך לסייע לרמ"ד (ראש המדור) בניהול ההון האנושי: פרופילי חיילים, צוותים, שיחות 1-על-1, נע"תים (נושאי אחריות תחומיים), שחרורים קרובים וחוזי חניכה.

הנחיות לשיחה:
- ענה תמיד בעברית טבעית, זורמת, חמה ומקצועית – בדיוק כמו בשיחה מול ChatGPT או Gemini, וללא תבניות רובוטיות.
- השתמש בכלים (Functions) כדי לקבל מידע על חיילים, לתעד שיחות 1-על-1, להקצות נע"ת, או לבדוק שחרורים.
- נסח את התשובה בצורה ברורה, מכבדת ומעצימה, תוך דגש על פיתוח אישי של החיילים, דאגה לרווחתם ומעקב שגרות פיקוד.
"""


class HRAgent:
    def __init__(self, repo: TaskRepository, api_key: Optional[str] = None):
        self.repo = repo
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.llm = LLMClient(api_key=self.api_key) if self.api_key else None

    async def handle_message(self, text: str, history: Optional[list[dict[str, Any]]] = None) -> str:
        if self.llm:
            tools = [
                {
                    "name": "get_soldier_profile",
                    "description": "קבלת פרופיל חייל מלא כולל צוות, דרגה, סטטוס ת\"ש, מצטיין/אקדמי, תאריך שחרור, נע\"ת והערות",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל המלא או החלקי"}
                        },
                        "required": ["soldier_name"],
                    },
                },
                {
                    "name": "list_soldiers_by_team",
                    "description": "הצגת רשימת החיילים המשובצים בצוות מסוים",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "team_name": {"type": "STRING", "description": "שם הצוות"}
                        },
                        "required": ["team_name"],
                    },
                },
                {
                    "name": "record_one_on_one",
                    "description": "תיעוד שיחת 1-על-1 אישית שבוצעה עם חייל והערות מהשיחה",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל"},
                            "notes": {"type": "STRING", "description": "עיקרי השיחה והתובנות האישיות/מקצועיות"}
                        },
                        "required": ["soldier_name", "notes"],
                    },
                },
                {
                    "name": "assign_naat",
                    "description": "שיבוץ או עדכון נע\"ת (נושא אחריות תחומי/תפקיד משני) לחייל",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל"},
                            "duty_name": {"type": "STRING", "description": "שם הנע\"ת/התפקיד"}
                        },
                        "required": ["soldier_name", "duty_name"],
                    },
                },
                {
                    "name": "get_upcoming_releases",
                    "description": "בדיקת חיילים שמשתחררים בתקופה הקרובה",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "months_ahead": {"type": "INTEGER", "description": "כמות החודשים קדימה (למשל 3 או 6)"}
                        },
                        "required": ["months_ahead"],
                    },
                },
                {
                    "name": "get_soldier_naat_history",
                    "description": "קבלת היסטוריית כל הנע\"תים שביצע החייל בעבר ובהווה",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל"}
                        },
                        "required": ["soldier_name"],
                    },
                },
                {
                    "name": "update_mentorship_contract",
                    "description": "הגדרה או עדכון של חוזה חניכה שנתי לחייל (יעד אישי ויעד מקצועי)",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל"},
                            "personal_goal": {"type": "STRING", "description": "יעד אישי/מנהיגותי"},
                            "professional_goal": {"type": "STRING", "description": "יעד טכנולוגי/מקצועי"}
                        },
                        "required": ["soldier_name", "personal_goal", "professional_goal"],
                    },
                },
                {
                    "name": "list_teams",
                    "description": "הצגת רשימת כל הצוותים במדור, כולל שמות הצוותים, ראשי הצוותים (רש\"צים) ומספר החיילים בכל צוות",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
                {
                    "name": "get_section_summary",
                    "description": "תמונת מצב מקיפה של כוח האדם במדור: כמות צוותים, סד\"כ חיילים כולל, התפלגות חובה/קבע ודרגות/קצונה",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
                {
                    "name": "get_mentorship_contract",
                    "description": "הצגת חוזה החניכה השנתי של חייל (יעדים, מועד שיחת 1-על-1 אחרונה ותאריך יעד הבא)",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "soldier_name": {"type": "STRING", "description": "שם החייל"}
                        },
                        "required": ["soldier_name"],
                    },
                },
            ]

            async def tool_executor(name: str, args: dict[str, Any]) -> Any:
                if name == "list_teams" or name == "get_section_summary":
                    return self.repo.get_section_summary()
                elif name == "get_soldier_profile":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא במערכת"}
                    team = self.repo.get_team(soldier.team_id) if soldier.team_id else None
                    return {
                        "full_name": soldier.full_name,
                        "team": team.name if team else "ללא צוות",
                        "service_type": soldier.service_type,
                        "rank": soldier.rank,
                        "tash_status": soldier.tash_status,
                        "academic_status": soldier.academic_status,
                        "excellence_status": soldier.excellence_status,
                        "release_date": soldier.release_date,
                        "current_naat": soldier.current_naat,
                        "commander_notes": soldier.commander_notes,
                    }
                elif name == "list_soldiers_by_team":
                    tname = (args.get("team_name") or "").strip()
                    if not tname or tname in ["כל הצוותים", "הצוותים שלי", "צוותים"]:
                        return self.repo.get_section_summary()
                    team = self.repo.get_team_by_name(tname)
                    if not team:
                        all_t = self.repo.list_teams()
                        matched_t = [t for t in all_t if tname in t.name or t.name in tname]
                        if matched_t:
                            team = matched_t[0]
                    if not team:
                        available_names = [t.name for t in self.repo.list_teams()]
                        return {"error": f"צוות '{tname}' לא נמצא. הצוותים הקיימים במדור הם: {available_names}"}
                    soldiers = self.repo.list_soldiers(team_id=team.id)
                    return {
                        "team": team.name,
                        "team_lead": team.team_lead_name or "טרם הוגדר רש\"צ רשמי",
                        "soldiers": [s.full_name for s in soldiers],
                        "count": len(soldiers),
                    }
                elif name == "record_one_on_one":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא"}
                    contract = self.repo.record_one_on_one_meeting(soldier.id, notes=args.get("notes"))
                    return {"status": "success", "soldier": soldier.full_name, "contract": contract}
                elif name == "assign_naat":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא"}
                    self.repo.assign_naat(soldier.id, args["duty_name"])
                    return {"status": "success", "soldier": soldier.full_name, "duty": args["duty_name"]}
                elif name == "get_upcoming_releases":
                    months = args.get("months_ahead", 3)
                    days = months * 30
                    releases = self.repo.get_upcoming_releases(days_ahead=days)
                    return {"releases": [{"full_name": r.full_name, "release_date": r.release_date} for r in releases]}
                elif name == "get_soldier_naat_history":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא"}
                    history_items = self.repo.get_naat_history(soldier.id)
                    return {"soldier": soldier.full_name, "history": history_items}
                elif name == "update_mentorship_contract":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא"}
                    res = self.repo.set_mentorship_goals(
                        soldier.id,
                        personal_goal=args.get("personal_goal", ""),
                        professional_goal=args.get("professional_goal", ""),
                    )
                    return {"status": "success", "soldier": soldier.full_name, "contract": res}
                elif name == "get_mentorship_contract":
                    soldier = self.repo.get_soldier_by_name(args["soldier_name"])
                    if not soldier:
                        return {"error": f"חייל בשם '{args['soldier_name']}' לא נמצא"}
                    contract = self.repo.get_mentorship_contract(soldier.id)
                    return {"soldier": soldier.full_name, "contract": contract}
                return {"error": f"Unknown tool {name}"}

            return await self.llm.chat(
                system_instruction=HR_SYSTEM_INSTRUCTION,
                user_message=text,
                history=history,
                tools=tools,
                tool_executor=tool_executor,
            )

        return self._fallback_handle_message(text)

    def _fallback_handle_message(self, text: str) -> str:
        # 0. Record 1-on-1 meeting: e.g. "ביצעתי שיחת 1-על-1 עם דניאל כהן: דיברנו על יעדים אישיים"
        if any(w in text for w in ["שיחת 1-על-1", "שיחה 1-על-1", "שיחה אישית"]) and any(w in text for w in ["ביצעתי", "קיימתי", "תיעדתי", "רשום", "סיימתי"]):
            match = re.search(r"(?:ביצעתי|קיימתי|תיעדתי|רשום|סיימתי)\s*שיח(?:ת|ה)\s*(?:1-על-1|אישית)\s*(?:עם)?\s*([^:]+):\s*(.+)$", text)
            if match:
                soldier_name = match.group(1).strip()
                notes = match.group(2).strip()
                return self.record_one_on_one(soldier_name, notes)

        # 1. Update mentorship contract: e.g. "עדכן חוזה חניכה לדניאל כהן: יעד אישי: ביטחון עצמי, יעד מקצועי: מומחה פייתון"
        if "חוזה חניכה" in text and any(w in text for w in ["עדכן", "קבע", "הגדר", "רשום", "שמור", "צור"]):
            match = re.search(r"חוזה\s*חניכה\s*(?:ל|עבור)?\s*([^:]+):\s*(.+)$", text)
            if match:
                soldier_name = match.group(1).strip()
                goals_text = match.group(2).strip()
                return self.update_mentorship_contract(soldier_name, goals_text)

        # 2. Query mentorship contract: e.g. "הצג חוזה חניכה דניאל כהן"
        if "חוזה חניכה" in text and any(w in text for w in ["הצג", "מהו", "פרטי", "בדוק", "סטטוס"]):
            match = re.search(r"חוזה\s*חניכה\s*(?:ל|של)?\s*([^\?\.\n]+)", text)
            if match:
                soldier_name = match.group(1).strip()
                soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
                return self.get_mentorship_contract_report(soldier_name)

        # 3. Upcoming releases query: e.g. "מי משתחרר ב-3 החודשים הקרובים?"
        if any(w in text for w in ["משתחרר", "משתחררים", "שחרור"]):
            days_ahead = 90
            months = 3
            if any(k in text for k in ["6", "חצי שנה", "180"]):
                days_ahead = 180
                months = 6
            return self.get_upcoming_releases_report(days_ahead=days_ahead, months_label=months)

        # 4. Assign na'at: e.g. "שבץ נע"ת לאורי לוי: אחראי הדרכה"
        if any(w in text for w in ["שבץ נע\"ת", "הקצה נע\"ת", "עדכן נע\"ת"]):
            assign_match = re.search(r"(?:שבץ|הקצה|עדכן)\s*נע\"ת\s*(?:ל|עבור)?\s*([^:]+):\s*(.+)$", text)
            if assign_match:
                soldier_name = assign_match.group(1).strip()
                duty_name = assign_match.group(2).strip()
                return self.assign_naat_to_soldier(soldier_name, duty_name)

        # 5. Query na'at history: e.g. "היסטוריית נע"ת אורי לוי"
        if "היסטוריית נע\"ת" in text or "היסטוריה של נע\"ת" in text or "נע\"תים של" in text:
            name_match = re.search(r"(?:היסטוריית נע\"ת|נע\"תים של)\s*(?:ל|של)?\s*([^\?\.\n]+)", text)
            if name_match:
                soldier_name = name_match.group(1).strip()
                soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
                return self.get_soldier_naat_history(soldier_name)

        # 6. Query all teams / section overview
        if any(w in text for w in ["מה הצוותים", "כמה צוותים", "רשימת צוותים", "הצוותים שלי", "כל הצוותים"]):
            summary = self.repo.get_section_summary()
            lines = [f"👥 *תמונת מצב צוותים במדור* (סה\"כ {summary['total_teams']} צוותים, {summary['total_soldiers']} חיילים):"]
            for tm in summary["teams"]:
                lead_str = f" | רש\"צ: {tm['team_lead']}" if tm['team_lead'] != "טרם הוגדר רש\"צ רשמי" else ""
                lines.append(f"• *צוות {tm['team_name']}* ({tm['soldiers_count']} חיילים){lead_str}")
            return "\n".join(lines)

        # 7. Query soldiers by specific team
        team_match = re.search(r"(?:בצוות|צוות)\s*([^\?\.\n]+)", text)
        if team_match and ("חיילים" in text or "מי בצוות" in text or "רשימת" in text):
            team_name = team_match.group(1).strip()
            team_name = re.sub(r"[\?\.\!]", "", team_name).strip()
            return self.list_soldiers_by_team(team_name)

        # 7. Query individual soldier profile
        soldier_match = re.search(r"(?:פרופיל(?:\s+חייל)?|מי זה|מי זאת|פרטי חייל|ספר לי על)\s*([^\?\.\n]+)", text)
        if soldier_match:
            soldier_name = soldier_match.group(1).strip()
            soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
            return self.get_soldier_profile(soldier_name)

        # Check if the text directly matches or contains a soldier's name from DB
        clean_text = re.sub(r"[\?\.\!\:\,]", "", text).strip()
        matched_soldier = self.repo.get_soldier_by_name(clean_text)
        if matched_soldier:
            return self.get_soldier_profile(matched_soldier.full_name)

        return "👥 סוכן כוח אדם ופיתוח: לשירותך בבירור פרטי חיילים, חלוקת צוותים, נע\"תים וחוזי חניכה."

    def record_one_on_one(self, soldier_name: str, notes: str) -> str:
        soldier = self.repo.get_soldier_by_name(soldier_name)
        if not soldier or soldier.id is None:
            return f"⚠️ לא נמצא חייל בשם '{soldier_name}' במערכת."

        contract = self.repo.record_one_on_one_meeting(soldier_id=soldier.id, notes=notes)
        next_due = contract.get("next_one_on_one_due") if contract else "לא ידוע"

        return (
            f"✅ *תועדה שיחת 1-על-1 בהצלחה!*\n"
            f"• *חייל*: {soldier.full_name}\n"
            f"• *תאריך היעד לשיחה הבאה*: {next_due}\n"
            f"• *סיכום*: {notes}"
        )

    def update_mentorship_contract(self, soldier_name: str, goals_text: str) -> str:
        soldier = self.repo.get_soldier_by_name(soldier_name)
        if not soldier or soldier.id is None:
            return f"⚠️ לא נמצא חייל בשם '{soldier_name}' במערכת."

        personal_goal = "טרם הוגדר"
        professional_goal = "טרם הוגדר"

        p_match = re.search(r"יעד\s*אישי:\s*([^,;]+)", goals_text)
        if p_match:
            personal_goal = p_match.group(1).strip()

        prof_match = re.search(r"יעד\s*מקצועי:\s*([^,;]+)", goals_text)
        if prof_match:
            professional_goal = prof_match.group(1).strip()

        # Fallback if no explicit prefix
        if personal_goal == "טרם הוגדר" and professional_goal == "טרם הוגדר" and "," in goals_text:
            parts = goals_text.split(",", 1)
            personal_goal = parts[0].strip()
            professional_goal = parts[1].strip()

        self.repo.set_mentorship_goals(
            soldier_id=soldier.id,
            personal_goal=personal_goal,
            professional_goal=professional_goal,
            year=2026,
        )

        return (
            f"📜 *עודכן חוזה חניכה עבור {soldier.full_name}*:\n"
            f"• *יעד אישי*: {personal_goal}\n"
            f"• *יעד מקצועי*: {professional_goal}"
        )

    def get_mentorship_contract_report(self, soldier_name: str) -> str:
        soldier = self.repo.get_soldier_by_name(soldier_name)
        if not soldier or soldier.id is None:
            return f"⚠️ לא נמצא חייל בשם '{soldier_name}' במערכת."

        contract = self.repo.get_mentorship_contract(soldier.id, year=2026)
        if not contract:
            return f"📜 טרם נפתח חוזה חניכה לשנת 2026 עבור {soldier.full_name}."

        last_date = contract.get("last_one_on_one_date") or "טרם בוצעה שיחה"
        next_due = contract.get("next_one_on_one_due") or "טרם נקבע יעד"

        return (
            f"📜 *חוזה חניכה עבור {soldier.full_name}* (שנת 2026):\n"
            f"• *יעד אישי*: {contract['personal_goal']}\n"
            f"• *יעד מקצועי*: {contract['professional_goal']}\n"
            f"• *שיחת 1-על-1 אחרונה*: {last_date}\n"
            f"• *יעד לשיחה הבאה*: {next_due}"
        )

    def get_upcoming_releases_report(self, days_ahead: int, months_label: int) -> str:
        soldiers = self.repo.get_upcoming_releases(days_ahead=days_ahead)
        if not soldiers:
            return f"🎖️ אין חיילים המשתחררים ב-{months_label} החודשים הקרובים."

        lines = [f"🎖️ *חיילים משתחררים ב-{months_label} החודשים הקרובים* ({len(soldiers)}):"]
        for s in soldiers:
            lines.append(f"• *{s.full_name}* [{s.service_type}] - תאריך שחרור: {s.release_date}")

        return "\n".join(lines)

    def assign_naat_to_soldier(self, soldier_name: str, duty_name: str) -> str:
        soldier = self.repo.get_soldier_by_name(soldier_name)
        if not soldier or soldier.id is None:
            return f"⚠️ לא נמצא חייל בשם '{soldier_name}' במערכת."

        old_duty = soldier.current_naat or "ללא נע\"ת"
        self.repo.assign_naat(soldier_id=soldier.id, duty_name=duty_name)

        return (
            f"✅ *עודכן נע\"ת עבור {soldier.full_name}*: *{duty_name}*\n"
            f"• נע\"ת קודם ({old_duty}) תועד בהיסטוריה."
        )

    def get_soldier_naat_history(self, soldier_name: str) -> str:
        soldier = self.repo.get_soldier_by_name(soldier_name)
        if not soldier or soldier.id is None:
            return f"⚠️ לא נמצא חייל בשם '{soldier_name}' במערכת."

        history = self.repo.get_naat_history(soldier.id)
        if not history:
            return f"📋 אין היסטוריית נע\"תים מתועדת עבור {soldier.full_name}."

        lines = [f"📋 *היסטוריית נע\"ת עבור {soldier.full_name}*:"]
        for h in history:
            end_label = f"עד {h['end_date']}" if h.get("end_date") else "פעיל כיום"
            lines.append(f"• *{h['duty_name']}* ({h['start_date']} - {end_label})")

        return "\n".join(lines)

    def get_soldier_profile(self, name: str) -> str:
        soldier = self.repo.get_soldier_by_name(name)
        if not soldier:
            return f"⚠️ לא נמצא חייל בשם '{name}' במאגר המדור."

        team_name = "לא משובץ לצוות"
        if soldier.team_id:
            team = self.repo.get_team(soldier.team_id)
            if team:
                team_name = team.name

        rank_str = f" [{soldier.rank}]" if soldier.rank else ""
        lines = [
            f"👤 *כרטיס חייל: {soldier.full_name}*{rank_str}",
            f"• *צוות*: {team_name}",
            f"• *סוג שירות*: {soldier.service_type}",
        ]
        if soldier.tash_status:
            lines.append(f"• *התאמות ת\"ש / מעמד מיוחד*: {soldier.tash_status}")
        if soldier.release_date:
            lines.append(f"• *תאריך שחרור/סיום*: {soldier.release_date}")
        if soldier.current_naat:
            lines.append(f"• *נע\"ת נוכחי*: {soldier.current_naat}")
        if soldier.academic_status or soldier.education:
            acad_parts = []
            if soldier.academic_status:
                acad_parts.append(soldier.academic_status)
            if soldier.education:
                acad_parts.append(soldier.education)
            lines.append(f"• *השכלה ואקדמיה*: {' - '.join(acad_parts)}")
        if soldier.excellence_status and soldier.excellence_status != "לא מועמד":
            exc_str = soldier.excellence_status
            if soldier.excellence_notes:
                exc_str += f" ({soldier.excellence_notes})"
            lines.append(f"• *הוקרה והצטיינות*: {exc_str}")
        if soldier.commander_notes:
            lines.append(f"• *הערות מפקד*: {soldier.commander_notes}")

        return "\n".join(lines)

    def list_soldiers_by_team(self, team_name: str) -> str:
        team = self.repo.get_team_by_name(team_name)
        if not team:
            if not team_name.startswith("צוות "):
                team = self.repo.get_team_by_name(f"צוות {team_name}")
            if not team:
                return f"⚠️ לא נמצא צוות בשם '{team_name}'."

        assert team.id is not None
        soldiers = self.repo.list_soldiers(team_id=team.id)
        if not soldiers:
            return f"👥 אין כרגע חיילים רשומים ב-{team.name}."

        lines = [f"👥 *חיילי {team.name}* ({len(soldiers)}):"]
        for s in soldiers:
            rank_info = f"{s.rank} " if s.rank else ""
            naat_info = f" (נע\"ת: {s.current_naat})" if s.current_naat else ""
            tash_info = f" [ת\"ש: {s.tash_status}]" if s.tash_status else ""
            lines.append(f"• *{rank_info}{s.full_name}* [{s.service_type}]{naat_info}{tash_info}")

        return "\n".join(lines)
