"""HR & People Agent logic."""
import re
from ramad_assistant.db.repository import TaskRepository


class HRAgent:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def handle_message(self, text: str) -> str:
        # 1. Upcoming releases query: e.g. "מי משתחרר ב-3 החודשים הקרובים?"
        if any(w in text for w in ["משתחרר", "משתחררים", "שחרור"]):
            days_ahead = 90
            months = 3
            if any(k in text for k in ["6", "חצי שנה", "180"]):
                days_ahead = 180
                months = 6
            return self.get_upcoming_releases_report(days_ahead=days_ahead, months_label=months)

        # 2. Assign na'at: e.g. "שבץ נע"ת לאורי לוי: אחראי הדרכה"
        if any(w in text for w in ["שבץ נע\"ת", "הקצה נע\"ת", "עדכן נע\"ת"]):
            assign_match = re.search(r"(?:שבץ|הקצה|עדכן)\s*נע\"ת\s*(?:ל|עבור)?\s*([^:]+):\s*(.+)$", text)
            if assign_match:
                soldier_name = assign_match.group(1).strip()
                duty_name = assign_match.group(2).strip()
                return self.assign_naat_to_soldier(soldier_name, duty_name)

        # 3. Query na'at history: e.g. "היסטוריית נע"ת אורי לוי"
        if "היסטוריית נע\"ת" in text or "היסטוריה של נע\"ת" in text or "נע\"תים של" in text:
            name_match = re.search(r"(?:היסטוריית נע\"ת|נע\"תים של)\s*(?:ל|של)?\s*([^\?\.\n]+)", text)
            if name_match:
                soldier_name = name_match.group(1).strip()
                soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
                return self.get_soldier_naat_history(soldier_name)

        # 4. Query soldiers by team
        team_match = re.search(r"(?:בצוות|צוות)\s*([^\?\.\n]+)", text)
        if team_match and ("חיילים" in text or "מי בצוות" in text or "רשימת" in text):
            team_name = team_match.group(1).strip()
            team_name = re.sub(r"[\?\.\!]", "", team_name).strip()
            return self.list_soldiers_by_team(team_name)

        # 5. Query individual soldier profile
        soldier_match = re.search(r"(?:פרופיל(?:\s+חייל)?|מי זה|פרטי חייל)\s*([^\?\.\n]+)", text)
        if soldier_match:
            soldier_name = soldier_match.group(1).strip()
            soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
            return self.get_soldier_profile(soldier_name)

        return "👥 סוכן כוח אדם ופיתוח: לשירותך בבירור פרטי חיילים, חלוקת צוותים, נע\"תים וחוזי חניכה."

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

        lines = [
            f"👤 *כרטיס חייל: {soldier.full_name}*",
            f"• *צוות*: {team_name}",
            f"• *סוג שירות*: {soldier.service_type}",
            f"• *תאריך שחרור*: {soldier.release_date or 'לא מוגדר'}",
            f"• *נע\"ת נוכחי*: {soldier.current_naat or 'ללא'}",
        ]
        if soldier.education:
            lines.append(f"• *השכלה*: {soldier.education}")
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
            naat_info = f" (נע\"ת: {s.current_naat})" if s.current_naat else ""
            lines.append(f"• *{s.full_name}* [{s.service_type}]{naat_info}")

        return "\n".join(lines)
