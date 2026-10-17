"""FastAPI Gateway server for Ramad Command Assistant."""
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ramad_assistant.adapters.base import IMessengerAdapter
from ramad_assistant.adapters.telegram import TelegramAdapter
from ramad_assistant.api.v1.soldiers import router as soldiers_router
from ramad_assistant.api.v1.tasks import router as tasks_router
from ramad_assistant.api.v1.agent import router as agent_router
from ramad_assistant.api.v1.notifications import router as notifications_router
from ramad_assistant.core.config import get_settings
from ramad_assistant.core.voice import IVoiceProcessor, GeminiVoiceProcessor
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.graph import Orchestrator


def create_app(
    messenger_adapter: Optional[IMessengerAdapter] = None,
    bot_token: Optional[str] = None,
    allowed_user_ids: Optional[list[str]] = None,
    task_repo: Optional[TaskRepository] = None,
    orchestrator: Optional[Orchestrator] = None,
    voice_processor: Optional[IVoiceProcessor] = None,
    api_secret: Optional[str] = None,
) -> FastAPI:
    settings = get_settings()
    effective_bot_token = bot_token or settings.telegram_bot_token
    effective_allowed_ids = (
        allowed_user_ids if allowed_user_ids is not None else settings.allowed_telegram_user_ids
    )
    effective_api_secret = api_secret or settings.api_secret

    app = FastAPI(
        title="Ramad Command Assistant Gateway & Mobile API",
        version="2.0.0",
        description="Unified REST API and Multi-Agent Orchestrator for Ramad Mobile Application",
    )

    # Enable CORS for Mobile Client and Local Development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    adapter = messenger_adapter or TelegramAdapter(bot_token=effective_bot_token)
    effective_voice_processor = voice_processor or GeminiVoiceProcessor(api_key=settings.gemini_api_key)

    effective_task_repo = task_repo or TaskRepository(db_url=settings.database_url)
    effective_task_repo.init_db()
    effective_orchestrator = orchestrator or Orchestrator(task_repo=effective_task_repo)

    # Attach shared dependencies to app state for API routes
    app.state.task_repo = effective_task_repo
    app.state.orchestrator = effective_orchestrator
    app.state.voice_processor = effective_voice_processor

    # Register REST API Routers
    app.include_router(soldiers_router)
    app.include_router(tasks_router)
    app.include_router(agent_router)
    app.include_router(notifications_router)

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

        # Handle incoming voice note (Voice-In / Text-Out)
        if unified_message.media_url and unified_message.media_type and unified_message.media_type.startswith("audio"):
            audio_bytes = await adapter.download_file(unified_message.media_url)
            if audio_bytes:
                transcription = await effective_voice_processor.process_audio(
                    audio_bytes=audio_bytes,
                    mime_type=unified_message.media_type,
                )
                if transcription:
                    unified_message.text = transcription

        # Process through LangGraph Orchestrator
        if unified_message.text and unified_message.user_id:
            response_text = await effective_orchestrator.process_message(
                user_id=unified_message.user_id,
                text=unified_message.text,
            )
            # Response is strictly returned as formatted text (Voice-In / Text-Out)
            await adapter.send_message(unified_message.user_id, response_text)

        return JSONResponse(status_code=200, content={"status": "ok"})

    @app.post("/cron/daily-briefing")
    async def trigger_daily_briefing(request: Request) -> JSONResponse:
        secret = request.headers.get("X-API-Secret")
        if not secret or secret != effective_api_secret:
            raise HTTPException(status_code=401, detail="Invalid API Secret")

        briefing_text = effective_orchestrator.task_agent.build_daily_briefing()

        # Send to primary section head recipient
        target_user = effective_allowed_ids[0] if effective_allowed_ids else "default"
        await adapter.send_message(target_user, briefing_text)

        return JSONResponse(status_code=200, content={"status": "briefing_sent"})

    @app.post("/cron/biweekly-reflection")
    async def trigger_biweekly_reflection(request: Request) -> JSONResponse:
        secret = request.headers.get("X-API-Secret")
        if not secret or secret != effective_api_secret:
            raise HTTPException(status_code=401, detail="Invalid API Secret")

        target_user = effective_allowed_ids[0] if effective_allowed_ids else "default"
        prompt_text = await effective_orchestrator.start_biweekly_reflection(user_id=target_user)
        await adapter.send_message(target_user, prompt_text)

        return JSONResponse(status_code=200, content={"status": "reflection_initiated"})

    return app
