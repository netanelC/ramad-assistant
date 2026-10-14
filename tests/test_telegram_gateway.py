import pytest
from httpx import ASGITransport, AsyncClient

from ramad_assistant.gateway.app import create_app
from ramad_assistant.adapters.telegram import TelegramAdapter


class SpyTelegramAdapter(TelegramAdapter):
    def __init__(self, bot_token: str = "fake-token"):
        super().__init__(bot_token=bot_token)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_telegram_webhook_parses_message_and_echoes_response():
    spy_adapter = SpyTelegramAdapter()
    app = create_app(messenger_adapter=spy_adapter)

    telegram_payload = {
        "update_id": 10001,
        "message": {
            "message_id": 42,
            "from": {
                "id": 999888,
                "is_bot": False,
                "first_name": "Netanel",
                "username": "netanel"
            },
            "chat": {
                "id": 999888,
                "type": "private"
            },
            "date": 1728560000,
            "text": "שלום בוט, זו בדיקת אקו"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=telegram_payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(spy_adapter.sent_messages) == 1
    recipient_id, text = spy_adapter.sent_messages[0]
    assert recipient_id == "999888"
    assert len(text) > 0
