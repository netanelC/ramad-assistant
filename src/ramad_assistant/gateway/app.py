"""FastAPI Gateway server for Ramad Command Assistant."""
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from ramad_assistant.adapters.base import IMessengerAdapter
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.core.config import get_settings
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.graph import Orchestrator


def create_app(
    messenger_adapter: Optional[IMessengerAdapter] = None,
    bot_token: Optional[str] = None,
    allowed_user_ids: Optional[list[str]] = None,
    task_repo: Optional[TaskRepository] = None,
    orchestrator: Optional[Orchestrator] = None,
) -> FastAPI:
    settings = get_settings()
    effective_bot_token = bot_token or settings.telegram_bot_token
    effective_allowed_ids = (
        allowed_user_ids if allowed_user_ids is not None else settings.allowed_telegram_user_ids
    )

    app = FastAPI(title="Ramad Command Assistant Gateway")
    adapter = messenger_adapter or TelegramAdapter(bot_token=effective_bot_token)

    effective_task_repo = task_repo or TaskRepository()
    effective_orchestrator = orchestrator or Orchestrator(task_repo=effective_task_repo)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        unified_message = await adapter.parse_inbound(payload)

        # Authorization check
        if effective_allowed_ids:
            if unified_message.user_id not in effective_allowed_ids:
                raise HTTPException(status_code=403, detail="Unauthorized user")

        # Process through LangGraph Orchestrator
        if unified_message.text and unified_message.user_id:
            response_text = await effective_orchestrator.process_message(
                user_id=unified_message.user_id,
                text=unified_message.text,
            )
            await adapter.send_message(unified_message.user_id, response_text)

        return JSONResponse(status_code=200, content={"status": "ok"})

    return app
