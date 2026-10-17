"""FastAPI Gateway server for Ramad Command Assistant & Mobile Client."""
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ramad_assistant.api.v1.soldiers import router as soldiers_router
from ramad_assistant.api.v1.tasks import router as tasks_router
from ramad_assistant.api.v1.agent import router as agent_router
from ramad_assistant.api.v1.notifications import router as notifications_router
from ramad_assistant.core.config import get_settings
from ramad_assistant.core.voice import IVoiceProcessor, GeminiVoiceProcessor
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.orchestrator.graph import Orchestrator


def create_app(
    task_repo: Optional[TaskRepository] = None,
    orchestrator: Optional[Orchestrator] = None,
    voice_processor: Optional[IVoiceProcessor] = None,
    api_secret: Optional[str] = None,
) -> FastAPI:
    settings = get_settings()
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

    effective_task_repo = task_repo or TaskRepository(db_url=settings.database_url)
    effective_task_repo.init_db()
    effective_orchestrator = orchestrator or Orchestrator(task_repo=effective_task_repo)
    effective_voice_processor = voice_processor or GeminiVoiceProcessor(api_key=settings.gemini_api_key)

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

    @app.post("/cron/daily-briefing")
    async def trigger_daily_briefing(request: Request) -> JSONResponse:
        secret = request.headers.get("X-API-Secret")
        if not secret or secret != effective_api_secret:
            raise HTTPException(status_code=401, detail="Invalid API Secret")

        briefing_text = effective_orchestrator.task_agent.build_daily_briefing()
        return JSONResponse(
            status_code=200,
            content={"status": "briefing_generated", "briefing": briefing_text},
        )

    @app.post("/cron/biweekly-reflection")
    async def trigger_biweekly_reflection(request: Request) -> JSONResponse:
        secret = request.headers.get("X-API-Secret")
        if not secret or secret != effective_api_secret:
            raise HTTPException(status_code=401, detail="Invalid API Secret")

        prompt_text = await effective_orchestrator.start_biweekly_reflection(user_id="app_user")
        return JSONResponse(
            status_code=200,
            content={"status": "reflection_initiated", "prompt": prompt_text},
        )

    return app
