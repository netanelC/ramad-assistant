"""LangGraph Orchestrator with Supervisor routing and persistence."""
from typing import Any, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.task_agent import TaskAgent
from ramad_assistant.orchestrator.hr_agent import HRAgent


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
        checkpointer: Optional[Any] = None,
    ):
        self.task_repo = task_repo
        self.task_agent = TaskAgent(task_repo=task_repo)
        self.hr_agent = HRAgent(repo=task_repo)
        self.checkpointer = checkpointer or InMemorySaver()
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
            if any(k in text for k in ["חייל", "חיילים", "צוות", "פרופיל", "משתחרר", "נע\"ת", "חוזה חניכה", "חניכה"]):
                return {"current_agent": "hr_agent"}

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

        # 4. Echo / General Node
        def echo_node(state: OrchestratorState) -> dict[str, Any]:
            text = state["input_text"]
            return {"response_text": f"קיבלתי: {text}"}

        builder.add_node("supervisor", supervisor_node)
        builder.add_node("task_agent", task_node)
        builder.add_node("hr_agent", hr_node)
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
                "echo_agent": "echo_agent",
            },
        )

        builder.add_edge("task_agent", END)
        builder.add_edge("hr_agent", END)
        builder.add_edge("echo_agent", END)

        return builder.compile(checkpointer=self.checkpointer)

    async def process_message(
        self, user_id: str, text: str, thread_id: Optional[str] = None
    ) -> str:
        tid = thread_id or f"thread_user_{user_id}"
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
