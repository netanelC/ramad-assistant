"""FastAPI Gateway server for Ramad Command Assistant."""
from typing import Any, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ramad_assistant.adapters.base import IMessengerAdapter
from ramad_assistant.adapters.telegram import TelegramAdapter


def create_app(
    messenger_adapter: Optional[IMessengerAdapter] = None,
    bot_token: str = "placeholder-token",
) -> FastAPI:
    app = FastAPI(title="Ramad Command Assistant Gateway")
    adapter = messenger_adapter or TelegramAdapter(bot_token=bot_token)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        unified_message = await adapter.parse_inbound(payload)

        # Baseline echo response for ticket #2
        if unified_message.text and unified_message.user_id:
            echo_text = f"קיבלתי: {unified_message.text}"
            await adapter.send_message(unified_message.user_id, echo_text)

        return JSONResponse(status_code=200, content={"status": "ok"})

    return app
