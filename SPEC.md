# Specification: Ramad Command Assistant (מערכת סוכנים לניהול מדורי ומנטורינג פיקודי)

## Problem Statement

A technology-intelligence section head (רמ"ד) leading ~30 people across 5 teams (mandatory soldiers, career officers, reservists, and consultants) faces an intense cognitive load. Operational fire drills, urgent production incidents, and organizational demands constantly threaten to derail command discipline. 

The section head is at risk of:
1. **Losing track of personal commitments and target deadlines (תג"בים)**, allowing follow-ups to slip through the cracks.
2. **Falling behind on command duties regarding people and mentorship**, specifically tracking the annual mentorship contracts (חוזי חניכה), monthly 1-on-1 meetings, and secondary duties (נע"תים) across a diverse workforce.
3. **Drifting into routine autopilot**, losing touch with field presence and the section head's personal command doctrine without dedicated time for self-reflection and candid self-debriefing.

Existing organizational tools (such as Jira on isolated military networks) focus strictly on team sprint boards and code tasks. The section head lacks a private, 24/7, frictionless personal command assistant accessible from their mobile device during commutes or movements across the base that can listen to voice notes, enforce accountability against their personal doctrine, and provide structured morning briefings and bi-weekly debriefs.

---

## Solution

The solution is a 24/7 cloud-based, serverless Multi-Agent Command Assistant accessible directly via Telegram (`Voice-In / Text-Out`), powered by Google Gemini and Supabase (PostgreSQL + pgvector). 

The assistant consists of:
1. **A Secure Gateway & Audio Pipeline**: Intercepts Telegram webhooks, authenticates the sender against an authorization whitelist, and ingests voice recordings (.oga/Opus) directly into Gemini's multimodal processing pipeline.
2. **A Supervisor & Semantic Router Agent**: Manages isolated conversation threads (מרחבי שיחה) using persistent LangGraph checkpoints, seamlessly distinguishing between ad-hoc operational commands and structured reflective dialogues.
3. **An HR & Mentorship Agent**: Maintains soldier profiles, tracks secondary duties (נע"ת), enforces the annual mentorship contract (חוזה חניכה) with two goals per soldier, and alerts on overdue monthly 1-on-1 meetings.
4. **A Task & Tagab Tracker Agent**: Manages the section head's personal task register and completion deadlines (תג"ב), dispatching an automated 07:00 AM daily briefing and tracking postponements with mandatory rationale.
5. **A Command Mentor Agent ("מראה פיקודית")**: Connects ad-hoc dilemmas to the section head's vectorized command doctrine using Socratic questioning, and runs an interactive, multi-turn bi-weekly self-debrief on Thursday afternoons around three non-negotiable doctrine questions to extract two points to preserve and two to improve.

---

## User Stories

### Interaction, Audio & Security
1. As a section head, I want to send natural language voice notes on Telegram while driving or walking, so that I can capture thoughts and tasks hands-free without typing.
2. As a section head, I want the system to always respond with formatted markdown text (Voice-In / Text-Out), so that I can review responses quickly and discreetly in meetings or noisy environments.
3. As a section head, I want all unauthorized Telegram users to be silently or strictly rejected at the gateway, so that sensitive section information and personal notes are never exposed to outsiders.
4. As a section head, I want the system to operate 24/7 in cloud serverless infrastructure, so that I never have to keep a local computer running or re-scan QR codes.
5. As a section head, I want all reminders, alerts, and briefings to strictly align with Jerusalem local time (`Asia/Jerusalem`), so that scheduled items trigger accurately regardless of daylight saving shifts.

### Task & Tagab Tracking
6. As a section head, I want to create a new task with a target completion deadline (תג"ב) by typing or speaking naturally (e.g. "תפתח משימה לתג"ב מחר בצהריים מול צוות 1"), so that the deadline is recorded without manual form entry.
7. As a section head, I want to assign a task to a specific team or soldier, so that I can easily group and follow up on commitments by organizational context.
8. As a section head, I want to mark a task as completed (DONE) or cancelled via chat, so that my task register remains accurate and current.
9. As a section head, I want to postpone a תג"ב by stating a new date and a mandatory reason, so that I maintain intentional discipline over postponed commitments rather than letting them slip silently.
10. As a section head, I want to ask for all open tasks or tasks due today at any time, so that I can regain immediate control of my daily priorities.
11. As a section head, I want to receive an automated morning briefing every day at 07:00 AM in Telegram, so that my day starts with a clear summary of overdue תג"בים, today's deadlines, and 48-hour critical alerts.

### People, Mentorship & Na'at Management
12. As a section head, I want to query a soldier's profile by full name or partial name, so that I can immediately view their team, service type, current נע"ת, release date, and commander notes.
13. As a section head, I want to view all soldiers belonging to a specific team, so that I can prepare for team status meetings or staffing reviews.
14. As a section head, I want to assign a new secondary duty (נע"ת) to a soldier and record the change in their history, so that duties are distributed fairly and soldiers are protected from burnout.
15. As a section head, I want to inspect a soldier's past נע"ת history, so that I can evaluate their organizational contribution during performance evaluations.
16. As a section head, I want to receive alerts about upcoming soldier release dates (3-month and 6-month horizons), so that I can plan transition pipelines and conduct timely discharge interviews.
17. As a section head, I want to establish and review an annual mentorship contract (חוזה חניכה) for each soldier containing two explicit goals (one personal and one professional), so that I fulfill my command obligation for soldier growth.
18. As a section head, I want to log a completed monthly 1-on-1 meeting with a soldier with brief notes, so that their next meeting due date resets for another 30 days.
19. As a section head, I want the morning briefing to alert me when any soldier has not had a 1-on-1 meeting for over 30 days, so that no team member is neglected during high-tempo periods.

### Command Mentor ("מראה פיקודית") & Bi-weekly Debrief
20. As a section head, I want to consult the mentor agent on an ad-hoc command dilemma, so that I receive Socratic reflection rooted in my command doctrine rather than generic advice.
21. As a section head, I want the system to initiate an interactive bi-weekly self-debrief session every other Thursday at 16:00, so that I am held accountable to my personal debrief routine.
22. As a section head, I want the debrief session to ask Question 1 ("האם נשאבתי לאוטומט?") and wait for my response, so that I examine my calendar, routine presence in the section, and field leadership.
23. As a section head, I want the debrief session to proceed to Question 2 ("האם הייתי האדם הכי נחוש בחדר ושמרתי על מקצועיות?"), so that I reflect on my composure, technical integrity, and hands-on code involvement.
24. As a section head, I want the debrief session to proceed to Question 3 ("האם ראיתי את האנשים שלי?"), so that I review my mentorship contracts, rights fulfillment, authentic feedback, and celebration of successes.
25. As a section head, I want the mentor agent to synthesize my responses at the end of the debrief into exactly two points to preserve and two points to improve, so that I have clear actionable takeaways for the next two weeks.
26. As a section head, I want past debrief records stored in the database, so that I can review personal progress and development patterns over time.

### Context Switching & Thread Isolation
27. As a section head, I want to be able to issue an urgent operational command (such as logging a new task) in the middle of an active debrief session, so that my operational workflow is never blocked.
28. As a section head, I want the system to process the operational command in the main user thread while keeping the debrief session paused in its dedicated thread, so that the two conversation contexts never pollute each other.
29. As a section head, I want to resume my debrief response whenever I am ready, so that the mentor agent seamlessly continues where we left off.

---

## Implementation Decisions

### Architectural Decisions & Messenger Boundary
- **Telegram as Primary Messenger for Phase 1**: Implemented via Telegram Bot API Webhook in accordance with ADR 0001, avoiding WhatsApp Cloud API 24-hour service window limitations and template pre-approval friction for proactive briefings and debriefs.
- **Port-and-Adapter Abstraction**: All core agent interactions communicate with an abstract `IMessengerAdapter` and `UnifiedMessage` domain model. Future integration with WhatsApp Cloud API will require only an adapter swap via environment variable configuration (`ACTIVE_MESSENGER=telegram`).
- **Voice-In / Text-Out Ingestion**: Audio files (`.oga` Opus recordings) arriving from Telegram are downloaded by the Gateway via authenticated Telegram Bot API calls and streamed directly into Google Gemini multimodal audio input, eliminating the need for a separate speech-to-text microservice. Outbound responses are strictly formatted text with Markdown.
- **Isolated Reflection Threads**: In accordance with ADR 0002, debrief sessions operate under isolated LangGraph threads (`thread_reflection_{YYYY-MM-DD}`) distinct from the standard daily thread (`thread_user_{user_id}`).
- **Stateless Serverless Execution with Persistent Checkpointing**: The application is deployed to Google Cloud Run with scale-to-zero capability. LangGraph conversation state is persisted across requests using `PostgresSaver` backed by Supabase.
- **Scheduled Automated Triggers**: Handled by Google Cloud Scheduler making authenticated HTTPS POST requests with an API secret header to:
  - `/cron/daily-briefing` (Daily at 07:00 AM Asia/Jerusalem).
  - `/cron/biweekly-reflection` (Every two weeks on Thursday at 16:00 Asia/Jerusalem).

### Modules & Responsibilities
- **Gateway Server**:
  - Validates webhook payloads and checks the incoming sender ID against `ALLOWED_TELEGRAM_USER_IDS`.
  - Dispatches media downloads for voice messages.
  - Serves scheduler trigger endpoints.
- **Supervisor & Semantic Router**:
  - Inspects inbound messages. If a bi-weekly debrief thread is currently active for today, semantically classifies whether the message is a debrief continuation or an ad-hoc operational command.
  - Routes requests to the appropriate thread and agent.
- **HR & Mentorship Module**:
  - Encapsulates tools for querying soldiers, teams, na'at history, and mentorship contracts.
  - Generates warning lists for soldiers whose 1-on-1 meeting is overdue (> 30 days).
- **Task & Tagab Module**:
  - Manages creation, listing, updating, and postponement of personal tasks and completion deadlines (תג"ב).
  - Assembles the morning briefing payload.
- **Command Mentor Module**:
  - Performs pgvector similarity search against chunked sections of `doctrine.md`.
  - Manages the 3-question multi-turn state machine for the bi-weekly self-debrief.
- **Database Layer**:
  - Supabase PostgreSQL instance housing domain tables, pgvector embeddings, and LangGraph checkpoint tables.

### Prototype Schema Shapes

```sql
-- Mentorship Contracts
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

-- Reflection Logs
CREATE TABLE reflection_logs (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    q1_automation_answer TEXT,
    q2_resolve_answer TEXT,
    q3_people_answer TEXT,
    points_to_preserve JSONB DEFAULT '[]'::jsonb,
    points_to_improve JSONB DEFAULT '[]'::jsonb,
    summary_insights TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Testing Decisions

### What Makes a Good Test
Tests must treat the system as a black box and verify external behavior through the highest available seam, rather than asserting on internal function calls, private agent state, or implementation details. 

A test is good if:
1. It drives the system exclusively through the external HTTP boundary (`POST /webhook/telegram` and `POST /cron/*`).
2. It asserts strictly on:
   - External messages sent to the user via the `IMessengerAdapter` spy (verifying message contents, Markdown format, and tone).
   - Observable persistent side-effects in the database (e.g. task created, 1-on-1 recorded, reflection logged).
3. It survives internal refactoring (e.g. prompt rewrites, sub-agent reorganizations) as long as the external conversational contract remains preserved.

### Modules Tested
- **HTTP Gateway & Security**: Verifying that unauthorized sender IDs receive a 403 / silent drop and authorized users trigger agent processing.
- **Voice Ingestion Pipeline**: Verifying that incoming voice payload triggers audio download and passes multimodal audio to the orchestrator.
- **Task & Tagab Workflows**: Verifying natural language task creation, query, completion, and postponement via simulated chat.
- **Mentorship & HR Workflows**: Verifying soldier lookup, goal updates, 1-on-1 logging, and overdue detection (> 30 days).
- **Scheduled Briefing**: Verifying that triggering `/cron/daily-briefing` delivers a complete Telegram briefing containing overdue תג"בים, today's תג"בים, and overdue 1-on-1 warnings.
- **Multi-turn Bi-weekly Debrief & Context Switching**: Verifying that triggering `/cron/biweekly-reflection` initiates Question 1, accepts multi-turn answers, tolerates an interleaved task creation in between without context pollution, and successfully records 2 preserve and 2 improve points upon completion.

### Test Environment & Prior Art
- **Integration Test Harness**: FastAPI `TestClient` executing against a live local or containerized PostgreSQL / Supabase test database.
- **External Spies & Mocks**:
  - The Telegram outbound API is mocked with an in-memory spy that captures sent messages for assertion.
  - The Gemini API client is stubbed with deterministic fixtures for predictable evaluation of LLM parsing and responses.

---

## Out of Scope

1. **Direct Jira Integration**: The system does not interface with, authenticate against, or synchronize tickets from the internal military Jira instance.
2. **External Calendar OAuth Integrations**: Google Calendar and Microsoft Outlook integrations are out of scope for Phase 1. Task deadlines and routines are managed via the internal database and Telegram notifications.
3. **Team Lead Internal Meetings**: The system does not monitor internal 1-on-1 sessions between team leads (רש"צים) and their subordinates. It tracks only the direct monthly meetings conducted by the section head.
4. **Voice Output (Text-to-Speech)**: The bot does not generate spoken audio responses. The interaction contract is strictly Voice-In / Text-Out.
5. **Multi-tenant Operations**: The application is tailored as a single-user private assistant for the section head. It does not support multiple user accounts or organizational tenancy.

---

## Further Notes

- **Domain Glossary**: All terminology in this specification adheres strictly to [`GLOSSARY.md`](./GLOSSARY.md) (תג"ב, חוזה חניכה, תחקור עצמי דו-שבועי, נע"ת, מראה פיקודית, מרחב שיחה).
- **Command Doctrine Alignment**: The Command Mentor agent's knowledge base is anchored in [`doctrine.md`](./doctrine.md).
- **Issue Tracking & Next Steps**: This repository currently operates without a configured remote issue tracker. To integrate with GitHub Issues or a specialized ticketing workflow in future steps, run `/setup-matt-pocock-skills` or configure remote origin credentials.
