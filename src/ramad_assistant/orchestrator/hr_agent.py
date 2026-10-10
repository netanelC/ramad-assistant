"""HR & People Agent logic."""
import re
from ramad_assistant.db.repository import TaskRepository


class HRAgent:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def handle_message(self, text: str) -> str:
        # 1. Query soldiers by team
        team_match = re.search(r"(?:בצוות|צוות)\s*([^\?\.\n]+)", text)
        if team_match and ("חיילים" in text or "מי בצוות" in text or "רשימת" in text):
            team_name = team_match.group(1).strip()
            # clean punctuation
            team_name = re.sub(r"[\?\.\!]", "", team_name).strip()
            return self.list_soldiers_by_team(team_name)

        # 2. Query individual soldier profile
        soldier_match = re.search(r"(?:פרופיל(?:\s+חייל)?|מי זה|פרטי חייל)\s*([^\?\.\n]+)", text)
        if soldier_match:
            soldier_name = soldier_match.group(1).strip()
            soldier_name = re.sub(r"[\?\.\!]", "", soldier_name).strip()
            return self.get_soldier_profile(soldier_name)

        return "👥 סוכן כוח אדם ופיתוח: לשירותך בבירור פרטי חיילים, חלוקת צוותים, נע\"תים וחוזי חניכה."

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
            # Try fuzzy or clean 'צוות 1'
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
