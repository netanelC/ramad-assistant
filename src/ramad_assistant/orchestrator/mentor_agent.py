"""Command Mentor Agent ('מראה פיקודית')."""
import os
from typing import Optional
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore


class CommandMentorAgent:
    def __init__(self, vector_store: DoctrineVectorStore, api_key: Optional[str] = None):
        self.vector_store = vector_store
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    async def consult(self, query: str) -> str:
        """Ad-hoc Socratic consultation based on doctrine principles."""
        query_emb = await self.vector_store.generate_embedding(query)
        top_chunks = self.vector_store.similarity_search(query_emb, top_k=2)

        relevant_section = ""
        relevant_content = ""
        if top_chunks:
            relevant_section = top_chunks[0]["section_title"]
            relevant_content = top_chunks[0]["content"]

        # Craft Socratic response based on doctrine context
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
