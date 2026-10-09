# Product Requirements Document (PRD)
## מערכת Multi-Agent מבוססת Telegram לניהול מדורי, תג"בים ומנטורינג פיקודי

---

### 1. סקירה כללית ומטרות (Executive Summary & Objectives)
מסמך זה מגדיר את הדרישות הפונקציונליות והטכניות עבור מערכת סוכנים חכמה (Multi-Agent System), הפועלת 24/7 בענן ומיועדת לשמש כעוזר פיקודי ואישי עבור ראש מדור (רמ"ד) טכנולוגי-מודיעיני. המערכת נגישה ישירות מהמכשיר הנייד של הרמ"ד (באמצעות Telegram Bot API בשלב א', עם הכנה מודולרית ל-WhatsApp Cloud API), ואינה תלויה בחומרה מקומית.

#### רקע תפעולי ומבצעי:
* **היקף כוח האדם**: כ-30 אנשים בחמישה צוותים (שילוב של חיילי חובה, אנשי קבע, משרתי מילואים ויועצים חיצוניים).
* **הפרדת עולמות משימתיים**: לצוותים קיימת מערכת JIRA ייעודית ברשת הצבאית. המערכת המוגדרת כאן מיועדת **אך ורק לניהול השוטף האישי של הרמ"ד** – מעקב תג"בים אישי, חלוקת קשב, בקרה על חוזי חניכה ושיחות 1-על-1, ותחקור פיקודי דו-שבועי.
* **אופי האינטראקציה**:
  * **Voice-In / Text-Out**: הרמ"ד יכול לשלוח הודעות קוליות (Voice Notes) בהליכה או בנהיגה, והמערכת מעבדת אותן ישירות ומשיבה בטקסט מעוצב וברור.
  * **שגרות פוש יזומות**: דוח בוקר יומי (07:00), התרעות תג"ב, ודיאלוג תחקור עצמי דו-שבועי מובנה (חמישי ב-16:00).

---

### 2. אילוצי סף ועקרונות תכנון (Invariants & Constraints)

1. **אבטחת מידע וסיווג (Information Security)**:
   * המערכת תכיל ותעבד **מידע בלתי מסווג בלבד**.
   * חל איסור מוחלט על הזנת פרטים מסווגים, מזהי מערכות סודיות או מידע מבצעי רגיש.
   * **בקרת גישה הרמטית (Access Control)**: שרת ה-Gateway מאמת את זהות השולח באמצעות Whitelist קשיח של `ALLOWED_TELEGRAM_USER_IDS`. הודעות ממשתמשים שאינם הרמ"ד נחסמות מיידית.
   * קיימת הכנה ארכיטקטונית לסוכן Guardrail עתידי לזיהוי ביטויים רגישים במידת הצורך.
2. **עלות אפסית עד זעירה ($0 - $5/month)**:
   * שימוש בשירותים מנוהלים בעלי Free Tier קבוע:
     * **Hosting**: Google Cloud Run (2 מיליון בקשות חודשיות חינם).
     * **Database & Memory**: Supabase (PostgreSQL + pgvector חינם).
     * **Scheduler**: Google Cloud Scheduler (3 משרות Cron חינם).
     * **LLM & Voice**: Google Gemini 2.5 / 3.8 Flash & Pro API דרך ה-Google GenAI SDK (תמיכה מובנית בקלט טקסט ושמע).
     * **Messaging**: Telegram Bot API הרשמי (חינם לחלוטין ללא הגבלת הודעות יזומות או חלונות 24 שעות).
3. **זמינות ורציפות 24/7 ללא תלות מקומית**:
   * ארכיטקטורת Serverless ללא תחנות קצה ביתיות, ללא סריקות QR וללא תלות ב-Daemon פעיל במחשב.
4. **עצמאות שכבת ההודעות (Hexagonal / Port-Adapter Pattern)**:
   * ליבת הסוכנים מתקשרת אך ורק מול מודל הודעות גנרי (`UnifiedMessage`).
   * שלב א' רץ על `TelegramAdapter`. מעבר עתידי ל-WhatsApp דורש החלפת משתנה סביבה בלבד ללא נגיעה בלוגיקת הסוכנים.
5. **שעון מקומי**:
   * כל התזמונים, התג"בים, הדוחות ושגרות התחקור מכוילים ל-Timezone מקומי: `Asia/Jerusalem`.

---

### 3. ארכיטקטורת המערכת (System Architecture)

```
                     ┌──────────────────────────────────────────────┐
                     │              Telegram Bot API                │
                     └──────────────────────┬───────────────────────┘
                                            │ Webhook (HTTPS POST)
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │            FastAPI Gateway Server            │
                     │  • Telegram Secret & User ID Whitelist       │
                     │  • Audio Downloader (Voice Notes .oga)       │
                     │  • Telegram Adapter -> UnifiedMessage        │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                      LangGraph Orchestrator (Stateful Multi-Agent)                          │
│                                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                            Supervisor / Router Agent                                  │  │
│  │  • Context & Thread Selector: thread_daily vs thread_reflection_{date}                │  │
│  │  • Intent Classification: Mentorship / Tasks / Reflection / General                   │  │
│  └───────────────────┬───────────────────────────┬──────────────────────────┬────────────┘  │
│                      │                           │                          │               │
│                      ▼                           ▼                          ▼               │
│         ┌─────────────────────────┐ ┌─────────────────────────┐ ┌────────────────────────┐ │
│         │   HR & People Agent     │ │   Task & Tagab Agent    │ │ Command Mentor Agent   │ │
│         │  (אנשים, חניכה ונע"ת)   │ │   (סוכן משימות ותג"ב)   │ │  (סוכן מראה פיקודית)   │ │
│         └────────────┬────────────┘ └────────────┬────────────┘ └───────────┬────────────┘ │
│                      │                           │                          │               │
└──────────────────────┼───────────────────────────┼──────────────────────────┼───────────────┘
                       │                           │                          │
                       ▼                           ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                          Supabase (PostgreSQL + pgvector Extension)                         │
│  • soldiers, teams, naat_history, mentorship_contracts, personal_tasks, reflection_logs     │
│  • command_doctrine (Embedded text chunks for RAG via pgvector)                             │
│  • checkpoints & checkpoint_blobs (LangGraph PostgresSaver persistence)                     │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                               ▲
                               │ Cron Trigger (HTTP POST with API Secret)
┌──────────────────────────────┴──────────────────────────────┐
│  Google Cloud Scheduler                                     │
│  • Daily 07:00 AM -> Trigger Daily Briefing Endpoint        │
│  • Hourly (08:00-20:00) -> Check Tagab SLA breaches         │
│  • Bi-weekly Thursday 16:00 PM -> Trigger Self-Debrief      │
└─────────────────────────────────────────────────────────────┘
```

---

### 4. אפיון הסוכנים ומרחבי השיחה (Multi-Agent & Thread Isolation)

#### 4.1. סוכן העל (Supervisor / Orchestrator Agent)
* **ייעוד**: ניתוח כוונת המשתמש, ניתוב סמנטי שקוף בין מרחבי שיחה (Threads), ושימור ה-State.
* **ניהול מרחבי שיחה מבודדים (Thread Isolation)**:
  * **מרחב שוטף (`thread_user_{user_id}`)**: מיועד לניהול משימות יומי, שליפת פרטי חיילים, ובירורים שוטפים.
  * **מרחב תחקור דו-שבועי (`thread_reflection_{YYYY-MM-DD}`)**: נוצר בכל יום חמישי של תחקור עצמי כדי לנהל את דיאלוג 3 השאלות ללא זליגת קונטקסט.
  * **ניתוב סמנטי שקוף (Seamless Routing)**: ה-Supervisor מזהה האם הודעת הרמ"ד מתייחסת לשאלת התחקור הפעילה או שמדובר בפקודה אופרטיבית (כגון פתיחת משימה/בירור), ומנתב ל-Thread המתאים ללא צורך בכפתורים או פקודות מיוחדות מצד הרמ"ד.

#### 4.2. סוכן אנשים, חניכה ופיתוח (HR & Mentorship Agent)
* **ייעוד**: ניהול מאגר 30 החיילים והיועצים בחמשת הצוותים, מעקב רציף אחר רווחתם, נע"תים, ושמירה על חובת הפיקוד בחוזי החניכה.
* **כלים (Tools)**:
  * `get_soldier_profile(name_or_id)`: שליפת כרטיס חייל מלא (צוות, סטטוס, נע"ת, תאריך שחרור, השכלה, הערות).
  * `list_soldiers_by_team(team_id, status)`: סינון לפי צוות וסוג שירות (חובה/קבע/מילואים/יועץ).
  * `update_soldier_info(soldier_id, fields)`: עדכון השכלה, תאריכים והערות מפקד.
  * `assign_naat(soldier_id, naat_name, start_date)`: הקצאת נע"ת חדש ותיעוד היסטוריית נע"תים למניעת שחיקה.
  * `get_upcoming_releases(days_ahead)`: איתור משתחררים בטווח מוגדר לתכנון שיחות 6 ו-3 חודשים מראש.
  * `get_mentorship_contract(soldier_id)`: שליפת חוזה חניכה (2 היעדים השנתיים – אישי ומקצועי, ותאריך שיחת 1-על-1 אחרונה).
  * `update_mentorship_goals(soldier_id, personal_goal, professional_goal)`: יצירה או עדכון של יעדי החוזה.
  * `record_one_on_one_meeting(soldier_id, summary_notes)`: תיעוד שיחת 1-על-1 חודשית של הרמ"ד ואיפוס שעון השיחה הבאה.
  * `get_overdue_mentorships(max_days=30)`: שליפת רשימת חיילים שעברו מעל 30 יום ללא שיחת 1-על-1 ישירה עם הרמ"ד.
* **התנהגות ואישיות**:
  * שיטתי, זוכר פרטים אישיים, מקפיד על מיצוי זכויות וחובת חניכה, ומתריע על חריגות מקצב שיחות ה-1-על-1.

#### 4.3. סוכן משימות ותג"ב (Task & Tagab Tracker Agent)
* **ייעוד**: ניהול יומן התג"בים האישי של הרמ"ד – מניעת מריחה, שכחה או פקקי בקרה. ממוקד אך ורק במשימות האישיות של הרמ"ד (ללא סנכרון כרטיסי Jira צבאיים).
* **כלים (Tools)**:
  * `create_task(title, tagab_datetime, priority, team_id, details)`: פתיחת משימה חדשה עם תאריך גמר ביצוע (תג"ב).
  * `update_task_status(task_id, status, notes)`: סגירת משימה, ביטול או עדכון התקדמות.
  * `postpone_task(task_id, new_tagab, reason)`: דחיית תג"ב עם חובת רישום סיבת הדחייה.
  * `get_daily_tasks(date)`: שליפת כל המשימות שמועד התג"ב שלהן חל היום.
  * `get_overdue_tasks()`: שליפת משימות שחרגו מהתג"ב ועדיין פתוחות.
* **לוגיקת דוח בוקר יומי (07:00 AM)**:
  * שליחת הודעת בוקר מובנית בטלגרם:
    1. **🚨 תג"בים שחורגים (Overdue)** – מודגשים בראש הרשימה.
    2. **📋 תג"בים להיום** – מסודרים לפי שעות פקיעה.
    3. **⏳ תג"בים קריטיים ל-48 השעות הקרובות**.
    4. **👥 סטטוס חניכה וכ"א**: חיילים שחרגו מ-30 יום ללא שיחת 1-על-1, ואירועי שחרור/נע"ת קרובים.

#### 4.4. סוכן "מראה פיקודית" ותחקור עצמי (Command Mentor & Reflection Agent)
* **ייעוד**: אתגור הרמ"ד בהתאם למסמך תפיסת הפיקוד שלו, שיקוף דילמות, וניהול שגרת התחקור העצמי הדו-שבועי.
* **מקור ידע (Knowledge Base)**:
  * מסמך התפיסה הפיקודית (`doctrine.md`) מאונדקס ב-Supabase pgvector.
* **מצבי פעולה**:
  1. **מצב התייעצות סוקרטית שוטפת (Ad-hoc Socratic Consultation)**:
     * כשהרמ"ד מתלבט או מעלה דילמה פיקודית, הסוכן שולף עקרונות רלוונטיים באמצעות Similarity Search ומחזיר שיקוף מעמת ומחדד במקום תשובות פשטניות.
  2. **דיאלוג תחקור עצמי דו-שבועי (Bi-weekly Self-Debrief - חמישי ב-16:00)**:
     * מופעל על ידי Google Cloud Scheduler אחת לשבועיים ביום חמישי בשעה 16:00.
     * מנהל שיחה רב-שלבית (Multi-turn) המציגה את 3 שאלות התפיסה המחייבות אחת אחרי השנייה:
       * **שאלה 1: האם נשאבתי לאוטומט?** (בדיקת ימי הילדות ביומן, סיבוב יומי במדור, נוכחות בשטח, תכנון שבועיים קדימה).
       * **שאלה 2: האם הייתי הבן אדם הכי נחוש בחדר ושמרתי על מקצועיות?** (קור רוח, הססנות בדיונים, חוב טכנולוגי, שריון זמן ללכלך ידיים בקוד).
       * **שאלה 3: האם ראיתי את האנשים שלי?** (שיחות חניכה, מיצוי זכויות, מתן פידבק דוגרי, חגיגת הצלחות, מתן גב פיקודי).
     * הרמ"ד עונה בקול או בטקסט, הסוכן מגיב בשיקוף קצר וממשיך לשאלה הבאה.
     * בסיום השיחה, הסוכן מזקק ושומר בטבלת `reflection_logs`: **2 נקודות לשימור ו-2 נקודות לשיפור עצמי** לשבועיים הבאים.

---

### 5. סכמת מסד הנתונים (Database Schema - PostgreSQL / Supabase DDL)

```sql
-- Enable Vector Extension for RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Teams Table
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    team_lead_name VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Soldiers Table
CREATE TABLE soldiers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    team_id INT REFERENCES teams(id) ON DELETE SET NULL,
    service_type VARCHAR(50) NOT NULL CHECK (service_type IN ('MANDATORY', 'CAREER', 'RESERVE', 'CONSULTANT')),
    release_date DATE,
    current_naat VARCHAR(150),
    education TEXT,
    commander_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Mentorship Contracts Table (חוזה חניכה ויעדי התפתחות)
CREATE TABLE mentorship_contracts (
    id SERIAL PRIMARY KEY,
    soldier_id INT REFERENCES soldiers(id) ON DELETE CASCADE,
    contract_year INT NOT NULL DEFAULT EXTRACT(YEAR FROM CURRENT_DATE),
    personal_goal TEXT NOT NULL,
    professional_goal TEXT NOT NULL,
    last_one_on_one_date DATE,
    next_one_on_one_due DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_soldier_contract_year UNIQUE (soldier_id, contract_year)
);

-- 4. Na'at (Secondary Duty) History Table
CREATE TABLE naat_history (
    id SERIAL PRIMARY KEY,
    soldier_id INT REFERENCES soldiers(id) ON DELETE CASCADE,
    duty_name VARCHAR(150) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    notes TEXT
);

-- 5. Personal Tasks & Tagabim Table
CREATE TABLE personal_tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    details TEXT,
    tagab_at TIMESTAMP WITH TIME ZONE NOT NULL,
    priority VARCHAR(20) DEFAULT 'MEDIUM' CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'DONE', 'CANCELLED', 'POSTPONED')),
    related_team_id INT REFERENCES teams(id) ON DELETE SET NULL,
    related_soldier_id INT REFERENCES soldiers(id) ON DELETE SET NULL,
    postpone_count INT DEFAULT 0,
    last_postpone_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Command Doctrine (RAG Chunks)
CREATE TABLE command_doctrine (
    id SERIAL PRIMARY KEY,
    section_title VARCHAR(150),
    content TEXT NOT NULL,
    embedding VECTOR(768), -- Gemini text-embedding dimension
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 7. Reflection Logs (תחקור עצמי דו-שבועי)
CREATE TABLE reflection_logs (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    q1_automation_answer TEXT,
    q2_resolve_answer TEXT,
    q3_people_answer TEXT,
    points_to_preserve JSONB DEFAULT '[]'::jsonb, -- 2 נקודות לשימור
    points_to_improve JSONB DEFAULT '[]'::jsonb,  -- 2 נקודות לשיפור
    summary_insights TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. LangGraph Persistence Tables
-- הוקמו ומנוהלות אוטומטית ע"י LangGraph PostgresSaver (checkpoints, checkpoint_blobs, checkpoint_writes).
```

---

### 6. ממשק ההודעות, עיבוד הקול ומתאמי השכבות (Messenger & Voice Pipeline)

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional

class UnifiedMessage(BaseModel):
    user_id: str
    channel: str  # 'telegram' or 'whatsapp'
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # 'audio/ogg', 'audio/mp3', etc.
    timestamp: str

class IMessengerAdapter(ABC):
    @abstractmethod
    async def parse_inbound(self, payload: dict) -> UnifiedMessage:
        """Parses webhook payload from Telegram/WhatsApp into UnifiedMessage."""
        pass

    @abstractmethod
    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Sends an outbound markdown text message to user."""
        pass
```

#### תהליך עיבוד הודעות קוליות (Voice Note Pipeline):
1. הרמ"ד שולח הקלטה קולית בטלגרם (פורמט קובץ `.oga` / קידוד Opus).
2. ה-FastAPI Gateway מזהה שדה `voice` בהודעת ה-Webhook, פונה ל-Telegram Bot API עם `getFile` ומוריד את קובץ השמע.
3. הקובץ מועבר ישירות כקלט מולטי-מודאלי ל-Gemini API (באמצעות `google-genai` SDK): המודל מעבד את האודיו ומבצע הבנת שפה ותמלול בהרצה יחידה.
4. הסוכנים ב-LangGraph מעבדים את הבקשה ומחזירים תשובה טקסטואלית בלבד (Voice-In / Text-Out).

---

### 7. תוכנית טעינת נתונים ראשונית (Initial Seeding)

#### תבנית קובץ חיילים וחוזי חניכה (`soldiers_seed.csv`):
```csv
full_name,team_name,service_type,release_date,current_naat,personal_goal,professional_goal,last_one_on_one_date
ישראל ישראלי,צוות 1,MANDATORY,2027-04-15,אחראי הוואי מדורי,ביטחון עצמי מול קהל,שליטה מלאה בארכיטקטורת ענן,2026-09-15
דניאל כהן,צוות 2,RESERVE,,חונך מקצועי,איזון מילואים-עבודה,הובלת מודול ה-AI,2026-09-20
שרה לוי,צוות 3,CAREER,2028-10-31,אחראית ידע,פיתוח מיומנויות חניכה,הסמכת פייתון מתקדם,2026-10-01
```

#### טעינת מסמך תפיסה פיקודית (`seed_doctrine.py`):
* הסקריפט קורא את קובץ [`doctrine.md`](./doctrine.md).
* מחלק את המסמך לפי ראשי פרקים (`##` ו-`###`).
* מייצר Embeddings באמצעות Gemini Embedding API.
* מאחסן בטבלת `command_doctrine` ב-Supabase לצורך שליפה סמנטית.

---

### 8. תוכנית עבודה ליישום עבור מפתח (Step-by-Step Implementation)

1. **שלב 1: הקמת תשתית ו-Supabase**:
   * יצירת פרויקט Supabase, הפעלת תוסף `vector`.
   * הרצת קובץ ה-DDL המעודכן בסעיף 5.
   * הרצת סקריפט `seed_doctrine.py` וטעינת נתוני החיילים וחוזי החניכה.
2. **שלב 2: בניית ליבת ה-Multi-Agent ב-LangGraph**:
   * הגדרת `PostgresSaver` לחיבור מול Supabase לשימור State.
   * מימוש ניתוב סמנטי בין מרחב שוטף למרחב תחקור דו-שבועי.
   * מימוש הכלים (Tools) עבור סוכן האנשים (כולל חוזי חניכה), סוכן המשימות וסוכן המראה הפיקודית.
3. **שלב 3: Gateway ומתאם Telegram עם Voice Pipeline**:
   * הקמת שרת `FastAPI` לקליטת Webhook מ-Telegram.
   * הוספת Middleware לאימות מזהה המשתמש מול `ALLOWED_TELEGRAM_USER_IDS`.
   * מימוש הורדת קובצי קול מטלגרם והזנתם ישירות ל-Gemini SDK.
4. **שלב 4: פריסה ל-Google Cloud Run ו-Cloud Scheduler**:
   * בניית `Dockerfile` מבוסס Python 3.11 והעלאה ל-Cloud Run.
   * הגדרת שתי משרות ב-Google Cloud Scheduler (שעון ירושלים):
     * `0 7 * * *` -> קריאה יומית ל-`/cron/daily-briefing`.
     * `0 16 */14 * 4` -> קריאה דו-שבועית בימי חמישי ל-`/cron/biweekly-reflection`.
5. **שלב 5: בדיקות קצה-לקצה**:
   * בדיקת פתיחת משימה בהודעה קולית וקבלת אישור בטקסט.
   * בדיקת דוח בוקר והתרעה על חייל שעבר 30 יום ללא שיחת 1-על-1.
   * סימולציית תחקור דו-שבועי רב-שלבי (3 שאלות התפיסה) ושמירת נקודות לשימור ושיפור.
