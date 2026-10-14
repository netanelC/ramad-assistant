"""Command Mentor Agent ('מראה פיקודית') and System Architect Advisor."""
import os
from typing import Any, Optional
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore
from ramad_assistant.orchestrator.llm_client import LLMClient

MENTOR_SYSTEM_INSTRUCTION = """אתה 'המנטור הפיקודי' (Command Mentor) והיועץ הראשי לרמ"ד (ראש מדור טכנולוגי-מודיעיני).
תפקידך לשמש "מראה פיקודית", יועץ סוקרטי, ומלווה אישי, וכן המומחה הראשי לארכיטקטורה וליכולות של מערכת העוזר (Ramad Assistant).

עקרונות הליבה הפיקודיים שלך (מהתפיסה הפיקודית):
1. שגרות ויומן: "מה שלא ביומן לא קורה!" שריון חלון תכנון שבועיים קדימה, דיונים של 30 דקות כברירת מחדל, וימי שלישי 16:00 יציאה הביתה למשפחה ולילדות.
2. אחריות מקיפה: "האויב של האחריות הוא אחריות מקיפה. קודם מוודאים שהקיים עובד הרמטית לפני שמוסיפים פיצ'רים חדשים. להגיד 'מה לא עושים'."
3. אנשים וחניכה: "הרמ"ד הוא המערכת. הפקודים רוצים שיראו אותם, שיילחמו בשבילם ושייתנו להם גב פיקודי מלא. שיחות 1-על-1 אישיות, דיאלוג ישיר ודוגרי."
4. איכות וחוב טכנולוגי: "אין חוב טכנולוגי שקוף! כל טלאי זמני חייב להיכנס מיד ל-Jira עם תאריך יעד ברור לתיקון ארכיטקטוני."
5. דוגמא אישית: קור רוח, אופטימיות, ומועילות מבצעית הקודמת ליעילות טכנולוגית.

ידע על ארכיטקטורת מערכת העוזר לרמ"ד:
המערכת היא מערכת Multi-Agent מודרנית הרצה בענן Google Cloud Run עם מסד נתונים SQLite/Postgres, ומחוברת לטלגרם (טקסט וקול באמצעות Gemini).
המערכת מורכבת מ-3 סוכנים מתמחים:
1. סוכן משימות ותג"בים (Task Agent): אחראי על ניהול משימות אישיות, מעקב תג"בים, דחיית תג"ב עם חובת רישום סיבה, סימון משימות שבוצעו, מחיקת משימות ודוחות בוקר יומיים.
2. סוכן כוח אדם ופיתוח (HR Agent): אחראי על תיקי חיילים, חלוקת צוותים, מעקב שיחות 1-על-1, נע"תים (נושאי אחריות תחומיים), שחרורים קרובים, וחוזי חניכה שנתיים.
3. סוכן מנטור פיקודי ושיחה כללית (Mentor Agent - אתה): מנהל שיחות פתוחות, דילמות מנהיגותיות, מראה פיקודית סוקרטית, שגרת תחקור עצמי דו-שבועי, ויודע להסביר על כל יכולות המערכת והארכיטקטורה שלה.

הנחיות לתשובה:
- ענה תמיד בעברית טבעית, חכמה, אמפתית ובוגרת כמו יועץ ושותף לדרך, ללא תבניות רובוטיות.
- אם מדובר בדילמה פיקודית או שאלת מנהיגות, השתמש בכלי 'search_doctrine' לחיפוש עקרונות רלוונטיים מתורת הפיקוד שלך.
- אם נשאלת על המערכת, תפקידי הסוכנים, או איך היא עובדת, הסבר בצורה בהירה ונעימה על הארכיטקטורה והיכולות.
- אם מדובר בברכה או סמול-טוק, פתח שיחה חמה ועניינית.
"""


class CommandMentorAgent:
    def __init__(self, vector_store: DoctrineVectorStore, api_key: Optional[str] = None):
        self.vector_store = vector_store
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.llm = LLMClient(api_key=self.api_key) if self.api_key else None

    async def consult(self, query: str, history: Optional[list[dict[str, Any]]] = None) -> str:
        """Ad-hoc Socratic consultation or general conversation based on doctrine and system knowledge."""
        if self.llm:
            tools = [
                {
                    "name": "search_doctrine",
                    "description": "חיפוש עקרונות ותובנות מתורת הפיקוד האישית של הרמ\"ד (מראה פיקודית)",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "ביטוי או נושא לחיפוש בתורת הפיקוד (למשל: עומס ביומן, חוב טכנולוגי, חניכה)",
                            }
                        },
                        "required": ["query"],
                    },
                }
            ]

            async def tool_executor(name: str, args: dict[str, Any]) -> Any:
                if name == "search_doctrine":
                    q = args.get("query", query)
                    q_emb = await self.vector_store.generate_embedding(q)
                    chunks = self.vector_store.similarity_search(q_emb, top_k=2)
                    return {"results": chunks}
                return {"error": f"Unknown tool: {name}"}

            return await self.llm.chat(
                system_instruction=MENTOR_SYSTEM_INSTRUCTION,
                user_message=query,
                history=history,
                tools=tools,
                tool_executor=tool_executor,
            )

        # Fallback for offline / testing without API key
        query_emb = await self.vector_store.generate_embedding(query)
        top_chunks = self.vector_store.similarity_search(query_emb, top_k=2)

        relevant_section = ""
        relevant_content = ""
        if top_chunks:
            relevant_section = top_chunks[0]["section_title"]
            relevant_content = top_chunks[0]["content"]

        return self._build_socratic_reflection(query, relevant_section, relevant_content)

    def _build_socratic_reflection(self, query: str, section_title: str, content: str) -> str:
        # Check specific thematic concerns
        if any(w in query for w in ["עומס", "שחיקה", "לו\"ז", "יומן", "זמן", "טובע"]):
            return (
                "🪞 *מראה פיקודית – שגרות יומן ועומסים*\n\n"
                "• *מהתפיסה הפיקודית שלך*: \"מה שלא ביומן – לא קורה! שריון חלון לתכנון לו\"ז שבועיים קדימה, וקביעת דיונים של 30 דקות כברירת מחדל.\"\n"
                "• *שאלה למחשבה*: האם היומן מנהל אותך או שאתה מנהל את היומן? האם פינית זמן קבוע לחלונות הבית והילדות, ואיפה אתה מוותר על דיונים שאינם בשרשרת הערך?"
            )

        if any(w in query for w in ["פיצ'ר", "פיתוח", "לחץ", "דרישה", "עוד פיצ'ר", "לקוח", "רע\"ן"]):
            return (
                "🪞 *מראה פיקודית – תפיסת אחריות ומצוינות*\n\n"
                "• *מהתפיסה הפיקודית שלך*: \"האויב של האחריות הוא אחריות מקיפה. קודם מוודאים שהקיים עובד הרמטית לפני שמוסיפים פיצ'רים חדשים. תסמונת ה'מה לא עושים'.\"\n"
                "• *שאלה למחשבה*: האם הפיצ'ר הזה משרת ישירות את שרשרת הערך של צרכן הקצה בסג\"ח? מה המחיר של אמירת 'כן' על היציבות והחוב הטכנולוגי של המערכת?"
            )

        if any(w in query for w in ["חייל", "פקוד", "מוטיבציה", "תסכול", "רש\"צ", "קליטה", "אנשים"]):
            return (
                "🪞 *מראה פיקודית – אנשים וחניכה*\n\n"
                "• *מהתפיסה הפיקודית שלך*: \"הרמ\"ד הוא המערכת. הפקודים רוצים שיראו אותם, שיילחמו בשבילם, ושניתן להם גב פיקודי מלא. דיאלוג ישיר ודוגרי.\"\n"
                "• *שאלה למחשבה*: האם עצרת לשיחת 1-על-1 אישית לבירור החסמים? האם הגדרתם חוזה חניכה ברור עם יעדים אישיים, או שאתה מצפה ממנו לנחש את הציפיות שלך?"
            )

        if any(w in query for w in ["חוב טכנולוגי", "באג", "טלאי", "קוד"]):
            return (
                "🪞 *מראה פיקודית – איכות וחוב טכנולוגי*\n\n"
                "• *מהתפיסה הפיקודית שלך*: \"אין חוב טכנולוגי שקוף! כל טלאי זמני חייב להיכנס מיד ל-Jira עם תאריך יעד ברור לתיקון ארכיטקטוני.\"\n"
                "• *שאלה למחשבה*: האם קיים תאריך יעד מוגדר לפתרון השורש, או שהטלאי הזמני עומד להפוך לקבוע?"
            )

        # Default Socratic reflection anchored in retrieved doctrine
        section_display = f" פרק: {section_title}" if section_title else ""
        return (
            f"🪞 *מראה פיקודית – אתגור סוקרטי*{section_display}\n\n"
            f"• *עקרון מנחה*: \"הובלה מתוך דוגמא אישית, קור רוח ואופטימיות. מועילות מבצעית קודמת ליעילות טכנולוגית.\"\n"
            f"• *שאלה למחשבה*: כיצד ההחלטה הזו מקדמת את המדור בחמשת צירי הערך (מודיעיני, מבצעי, מקצועי, אישי, עכשווי), והאם אתה פועל כאן מתוך אוטומט או מתוך בחירה מודעת?"
        )

    def start_debrief_prompt(self) -> str:
        return (
            "🪞 *שגרת תחקור עצמי דו-שבועי לרמ\"ד*\n\n"
            "שלום רמ\"ד, הגיע זמן העצירה וההתחככות העצמית (30 דקות בחמישי אחה\"צ).\n\n"
            "❓ *שאלה 1 מתוך 3: האם נשאבתי לאוטומט?*\n"
            "(בדוק את ימי הילדות והבית ביומן, סיבוב יומי במדור ונוכחות בשטח, ותכנון שבועיים קדימה)."
        )

    def process_debrief_turn(
        self,
        current_step: int,
        user_answer: str,
        q1_answer: Optional[str] = None,
        q2_answer: Optional[str] = None,
    ) -> tuple[str, int, Optional[dict]]:
        """
        Advances debrief state machine:
        step 1 -> user answered Q1, returns Q2, next step 2
        step 2 -> user answered Q2, returns Q3, next step 3
        step 3 -> user answered Q3, synthesizes 2 preserve / 2 improve, next step 4 (DONE)
        """
        if current_step == 1:
            reply = (
                "💭 *שיקוף שאלה 1 נרשם.*\n\n"
                "❓ *שאלה 2 מתוך 3: האם הייתי האדם הכי נחוש בחדר ושמרתי על מקצועיות?*\n"
                "(בדוק קור רוח ואופטימיות מול צוותים, חוב טכנולוגי שנרשם ב-Jira, ושריון זמן 'ללכלך את הידיים' בקוד)."
            )
            return reply, 2, None

        elif current_step == 2:
            reply = (
                "💭 *שיקוף שאלה 2 נרשם.*\n\n"
                "❓ *שאלה 3 מתוך 3: האם ראיתי את האנשים שלי?*\n"
                "(בדוק עמידה בשיחות חניכה ו-1-על-1, מיצוי זכויות ת\"ש/משא\"ן, משוב דוגרי, ומתן גב פיקודי)."
            )
            return reply, 3, None

        elif current_step == 3:
            # Final synthesis
            points_to_preserve = [
                "שמירה על קור רוח ודוגמא אישית בדיונים",
                "שריון חלונות יומן מוגדרים ליציאה לילדות ולמשפחה",
            ]
            points_to_improve = [
                "הקפדה מחמירה על תיעוד כל מעקף טכנולוגי ב-Jira",
                "סגירת פערים בשיחות 1-על-1 לכל החיילים ללא חריגה מ-30 יום",
            ]
            summary_insights = (
                f"תשובה לשאלה 1: {q1_answer or ''}\n"
                f"תשובה לשאלה 2: {q2_answer or ''}\n"
                f"תשובה לשאלה 3: {user_answer}"
            )
            data = {
                "q1_answer": q1_answer or "",
                "q2_answer": q2_answer or "",
                "q3_answer": user_answer,
                "points_to_preserve": points_to_preserve,
                "points_to_improve": points_to_improve,
                "summary_insights": summary_insights,
            }

            reply = (
                "🎯 *סיכום תחקור עצמי דו-שבועי*\n\n"
                "התחקור הושלם בהצלחה ותועד במערכת!\n\n"
                "📌 *2 נקודות לשימור לשבועיים הקרובים*:\n"
                f"1. {points_to_preserve[0]}\n"
                f"2. {points_to_preserve[1]}\n\n"
                "🔧 *2 נקודות לשיפור לשבועיים הקרובים*:\n"
                f"1. {points_to_improve[0]}\n"
                f"2. {points_to_improve[1]}"
            )
            return reply, 4, data

        return "שגרת התחקור הושלמה.", 4, None

