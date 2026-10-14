import os
import re
from typing import Any, Optional, TypedDict
import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore
from ramad_assistant.orchestrator.task_agent import TaskAgent
from ramad_assistant.orchestrator.hr_agent import HRAgent
from ramad_assistant.orchestrator.mentor_agent import CommandMentorAgent


class OrchestratorState(TypedDict):
    user_id: str
    thread_id: str
    input_text: str
    current_agent: str
    response_text: str
    history: list[dict[str, Any]]


class Orchestrator:
    def __init__(
        self,
        task_repo: TaskRepository,
        vector_store: Optional[DoctrineVectorStore] = None,
        checkpointer: Optional[Any] = None,
    ):
        self.task_repo = task_repo
        self.vector_store = vector_store or DoctrineVectorStore(repo=task_repo)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.task_agent = TaskAgent(task_repo=task_repo, api_key=self.gemini_api_key)
        self.hr_agent = HRAgent(repo=task_repo, api_key=self.gemini_api_key)
        self.mentor_agent = CommandMentorAgent(vector_store=self.vector_store, api_key=self.gemini_api_key)
        self.checkpointer = checkpointer or InMemorySaver()
        self.user_histories: dict[str, list[dict[str, str]]] = {}
        self.active_reflection_thread: Optional[str] = None
        self.reflection_step: int = 0
        self.reflection_data: dict[str, Any] = {}
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(OrchestratorState)

        # 1. Supervisor / Router Node (Semantic Classification with Fallback)
        async def supervisor_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            agent = await self._classify_intent(text)
            return {"current_agent": agent}

        # 2. Task Agent Node
        async def task_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            history = state.get("history") or []
            reply = await self.task_agent.handle_message(text, history=history)
            return {"response_text": reply}

        # 3. HR Agent Node
        async def hr_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            history = state.get("history") or []
            reply = await self.hr_agent.handle_message(text, history=history)
            return {"response_text": reply}

        # 4. Mentor Agent Node (Leadership & System Expert & General Conversation)
        async def mentor_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            history = state.get("history") or []
            reply = await self.mentor_agent.consult(text, history=history)
            return {"response_text": reply}

        builder.add_node("supervisor", supervisor_node)
        builder.add_node("task_agent", task_node)
        builder.add_node("hr_agent", hr_node)
        builder.add_node("mentor_agent", mentor_node)

        builder.add_edge(START, "supervisor")

        def route_next(state: OrchestratorState) -> str:
            return state.get("current_agent", "mentor_agent")

        builder.add_conditional_edges(
            "supervisor",
            route_next,
            {
                "task_agent": "task_agent",
                "hr_agent": "hr_agent",
                "mentor_agent": "mentor_agent",
            },
        )

        builder.add_edge("task_agent", END)
        builder.add_edge("hr_agent", END)
        builder.add_edge("mentor_agent", END)

        return builder.compile(checkpointer=self.checkpointer)

    async def start_biweekly_reflection(self, user_id: str, date_str: Optional[str] = None) -> str:
        from datetime import datetime, timezone
        d = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ref_thread_id = f"thread_reflection_{d}"
        self.active_reflection_thread = ref_thread_id
        self.reflection_step = 1
        self.reflection_data = {
            "session_date": d,
            "q1_answer": "",
            "q2_answer": "",
            "q3_answer": "",
        }
        return self.mentor_agent.start_debrief_prompt()

    async def process_message(
        self, user_id: str, text: str, thread_id: Optional[str] = None
    ) -> str:
        # Dynamic ADR-0002 thread routing: an operational command must be an explicit task or HR operation
        is_operational = self._is_operational_command(text)

        if not thread_id:
            if self.active_reflection_thread and not is_operational:
                # Part of ongoing reflection session
                tid = self.active_reflection_thread
            else:
                tid = f"thread_user_{user_id}"
        else:
            tid = thread_id

        # If routed to active reflection thread and debrief is in progress
        if tid == self.active_reflection_thread and not is_operational:
            reply, next_step, summary_data = self.mentor_agent.process_debrief_turn(
                current_step=self.reflection_step,
                user_answer=text,
                q1_answer=self.reflection_data.get("q1_answer"),
                q2_answer=self.reflection_data.get("q2_answer"),
            )
            if self.reflection_step == 1:
                self.reflection_data["q1_answer"] = text
            elif self.reflection_step == 2:
                self.reflection_data["q2_answer"] = text
            elif self.reflection_step == 3:
                self.reflection_data["q3_answer"] = text

            self.reflection_step = next_step

            if summary_data:
                # Save to reflection_logs
                from ramad_assistant.db.models import ReflectionLog
                log_entry = ReflectionLog(
                    session_date=self.reflection_data["session_date"],
                    q1_automation_answer=summary_data["q1_answer"],
                    q2_resolve_answer=summary_data["q2_answer"],
                    q3_people_answer=summary_data["q3_answer"],
                    points_to_preserve=summary_data["points_to_preserve"],
                    points_to_improve=summary_data["points_to_improve"],
                    summary_insights=summary_data["summary_insights"],
                )
                self.task_repo.save_reflection_log(log_entry)
                self.active_reflection_thread = None  # Debrief completed

            return reply

        # Otherwise route through standard LangGraph user thread
        config = {"configurable": {"thread_id": tid}}
        history = self.user_histories.get(user_id, [])
        initial_state: OrchestratorState = {
            "user_id": user_id,
            "thread_id": tid,
            "input_text": text,
            "current_agent": "supervisor",
            "response_text": "",
            "history": history[-15:],
        }
        result = await self.graph.ainvoke(initial_state, config=config)
        reply = result.get("response_text", "")

        # Update conversational history
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        self.user_histories[user_id].append({"role": "user", "text": text})
        self.user_histories[user_id].append({"role": "model", "text": reply})
        if len(self.user_histories[user_id]) > 20:
            self.user_histories[user_id] = self.user_histories[user_id][-20:]

        return reply

    async def _classify_intent(self, text: str) -> str:
        """
        Classifies incoming message into one of:
        - hr_agent: Questions or actions regarding soldiers, profiles, teams, 1-on-1s, na'at, releases, mentorship.
        - task_agent: Task creation, postponement, status updates, deletions, completions, tagab queries.
        - mentor_agent: Philosophical dilemmas, leadership reflections, system architecture questions, greetings, chit-chat.
        """
        if self.gemini_api_key:
            prompt = (
                "You are an intent classifier for a military tech-intelligence section head (רמ\"ד) assistant.\n"
                "Classify the following user message into exactly ONE category:\n"
                "- hr_agent: Inquiries, questions or commands regarding soldiers (חיילים, כ\"א), soldier profiles (מי זה, מי זאת, פרטים על חייל), "
                "teams (מי בצוות), 1-on-1 meetings (שיחות 1-על-1), secondary duties (נע\"ת), upcoming releases (שחרור), or mentorship contracts (חוזה חניכה).\n"
                "- task_agent: Creating tasks (תפתח משימה), updating deadlines/tagab (תג\"ב), postponing tasks (תדחה), completing/cancelling tasks (סיימתי, סיימתי את כל המשימות, בטל), deleting tasks (תמחק, מחק משימה, תמחק את כל המשימות), or querying task lists (מה המשימות, משימות פתוחות).\n"
                "- mentor_agent: Leadership dilemmas (דילמה פיקודית), calendar overload/burnout (עומס, שחיקה), Socratic reflection, questions about the system/architecture/how it works, or general greetings and open chat.\n\n"
                f"User message: \"{text}\"\n\n"
                "Return ONLY the category name (hr_agent, task_agent, mentor_agent) with no other text."
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20},
            }
            try:
                async with httpx.AsyncClient(timeout=3.5) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates") or []
                        if candidates:
                            raw_reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                            clean_agent = raw_reply.lower().replace("`", "").strip()
                            if clean_agent in ["hr_agent", "task_agent", "mentor_agent"]:
                                return clean_agent
            except Exception:
                pass  # Fallback to local rule-based routing

        return self._fallback_classify_intent(text)

    def _fallback_classify_intent(self, text: str) -> str:
        """Deterministic keyword and database entity matching fallback."""
        clean = re.sub(r"[\?\.\!\:\,]", "", text).strip()

        # 1. Check if the message mentions a soldier's name in the DB
        soldier = self.task_repo.get_soldier_by_name(clean)
        if soldier:
            return "hr_agent"

        # Check if any word combination matches a soldier
        words = clean.split()
        if len(words) >= 2:
            for i in range(len(words) - 1):
                candidate = f"{words[i]} {words[i+1]}"
                if self.task_repo.get_soldier_by_name(candidate):
                    return "hr_agent"

        # 2. Explicit task / tagab actions (create, delete, complete, postpone)
        if any(k in text for k in [
            "תפתח משימה", "צור משימה", "משימה חדשה", "תג\"ב", "תגבים",
            "תדחה", "דחה", "סיימתי משימה", "בטל משימה", "תמחק", "מחק", "למחוק",
            "סיימתי", "השלמתי"
        ]):
            return "task_agent"

        # 3. HR & People keywords
        if any(k in text for k in ["חייל", "חיילים", "צוות", "פרופיל", "משתחרר", "משתחררים", "שחרור", "נע\"ת", "חוזה חניכה", "חניכה", "1-על-1", "שיחה אישית", "מי זה", "מי זאת", "פרטי חייל", "ספר לי על"]):
            return "hr_agent"

        # 4. Command Mentor keywords
        if any(k in text for k in ["מראה פיקודית", "דילמה", "מתלבט", "עומס", "שחיקה", "טובע", "מתוסכל", "תפיסה פיקודית", "עקרונות"]):
            return "mentor_agent"

        # 5. General task queries
        if any(k in text for k in ["משימה", "משימות", "תזכורת", "task", "tagab", "postpone"]):
            return "task_agent"

        return "mentor_agent"

    def _is_operational_command(self, text: str) -> bool:
        """Determines if text is an explicit operational command rather than debrief continuation."""
        task_keywords = [
            "תפתח משימה", "צור משימה", "משימה חדשה", "תג\"ב", "תגבים",
            "תדחה", "דחה משימה", "סיימתי משימה", "בטל משימה",
            "תמחק", "מחק", "למחוק", "סיימתי", "השלמתי", "בטל"
        ]
        hr_keywords = ["מי בצוות", "רשימת צוות", "פרופיל חייל", "מי משתחרר", "שבץ נע\"ת", "הקצה נע\"ת", "היסטוריית נע\"ת", "עדכן חוזה חניכה", "הצג חוזה חניכה", "ביצעתי שיחת 1-על-1", "קיימתי שיחת 1-על-1"]
        query_keywords = ["משימות פתוחות", "משימות להיום", "הצג משימות", "רשימת משימות"]
        return any(k in text for k in task_keywords + hr_keywords + query_keywords)

