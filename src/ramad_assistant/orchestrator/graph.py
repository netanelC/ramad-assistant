"""LangGraph Orchestrator with Supervisor routing and persistence."""
from typing import Any, Optional, TypedDict
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


class Orchestrator:
    def __init__(
        self,
        task_repo: TaskRepository,
        vector_store: Optional[DoctrineVectorStore] = None,
        checkpointer: Optional[Any] = None,
    ):
        self.task_repo = task_repo
        self.vector_store = vector_store or DoctrineVectorStore(repo=task_repo)
        self.task_agent = TaskAgent(task_repo=task_repo)
        self.hr_agent = HRAgent(repo=task_repo)
        self.mentor_agent = CommandMentorAgent(vector_store=self.vector_store)
        self.checkpointer = checkpointer or InMemorySaver()
        self.active_reflection_thread: Optional[str] = None
        self.reflection_step: int = 0
        self.reflection_data: dict[str, Any] = {}
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(OrchestratorState)

        # 1. Supervisor / Router Node
        def supervisor_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            # Explicit task / tagab actions take precedence
            if any(k in text for k in ["תפתח משימה", "צור משימה", "משימה חדשה", "תג\"ב", "תגבים", "תדחה", "דחה", "סיימתי משימה", "בטל משימה"]):
                return {"current_agent": "task_agent"}

            # HR & People routing
            if any(k in text for k in ["חייל", "חיילים", "צוות", "פרופיל", "משתחרר", "נע\"ת", "חוזה חניכה", "חניכה", "1-על-1", "שיחה אישית"]):
                return {"current_agent": "hr_agent"}

            # Philosophical / Command Mentor / Reflection routing
            if any(k in text for k in ["מראה פיקודית", "דילמה", "מתלבט", "עומס", "שחיקה", "טובע", "מתוסכל", "תפיסה פיקודית", "עקרונות"]):
                return {"current_agent": "mentor_agent"}

            # General task routing
            if any(k in text for k in ["משימה", "משימות", "תזכורת", "task", "tagab", "postpone"]):
                return {"current_agent": "task_agent"}

            return {"current_agent": "echo_agent"}

        # 2. Task Agent Node
        def task_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            reply = self.task_agent.handle_message(text)
            return {"response_text": reply}

        # 3. HR Agent Node
        def hr_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            reply = self.hr_agent.handle_message(text)
            return {"response_text": reply}

        # 4. Mentor Agent Node
        async def mentor_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            reply = await self.mentor_agent.consult(text)
            return {"response_text": reply}

        # 5. Echo / General Node
        def echo_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            return {"response_text": f"קיבלתי: {text}"}

        builder.add_node("supervisor", supervisor_node)
        builder.add_node("task_agent", task_node)
        builder.add_node("hr_agent", hr_node)
        builder.add_node("mentor_agent", mentor_node)
        builder.add_node("echo_agent", echo_node)

        builder.add_edge(START, "supervisor")

        def route_next(state: OrchestratorState) -> str:
            return state.get("current_agent", "echo_agent")

        builder.add_conditional_edges(
            "supervisor",
            route_next,
            {
                "task_agent": "task_agent",
                "hr_agent": "hr_agent",
                "mentor_agent": "mentor_agent",
                "echo_agent": "echo_agent",
            },
        )

        builder.add_edge("task_agent", END)
        builder.add_edge("hr_agent", END)
        builder.add_edge("mentor_agent", END)
        builder.add_edge("echo_agent", END)

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
        # Dynamic ADR-0002 thread routing
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
        initial_state: OrchestratorState = {
            "user_id": user_id,
            "thread_id": tid,
            "input_text": text,
            "current_agent": "supervisor",
            "response_text": "",
        }
        result = await self.graph.ainvoke(initial_state, config=config)
        return result.get("response_text", "")

    def _is_operational_command(self, text: str) -> bool:
        """Determines if text is an explicit operational command rather than debrief continuation."""
        task_keywords = ["תפתח משימה", "צור משימה", "משימה חדשה", "תג\"ב", "תגבים", "תדחה", "דחה", "סיימתי משימה", "בטל משימה"]
        hr_keywords = ["חייל", "חיילים", "צוות", "פרופיל", "משתחרר", "נע\"ת", "חוזה חניכה", "1-על-1", "שיחה אישית"]
        query_keywords = ["משימות פתוחות", "משימות להיום", "הצג משימות", "רשימת משימות"]
        return any(k in text for k in task_keywords + hr_keywords + query_keywords)

