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


def make_telegram_payload(user_id: int, text: str = "שלום") -> dict:
    return {
        "update_id": 10001,
        "message": {
            "message_id": 42,
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "TestUser",
            },
            "chat": {
                "id": user_id,
                "type": "private"
            },
            "date": 1728560000,
            "text": text
        }
    }


@pytest.mark.asyncio
async def test_unauthorized_user_is_blocked_with_403():
    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"]
    )

    unauthorized_payload = make_telegram_payload(user_id=111222, text="שלום מזר")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=unauthorized_payload)

    assert response.status_code == 403
    assert response.json() == {"detail": "Unauthorized user"}
    assert len(spy_adapter.sent_messages) == 0


@pytest.mark.asyncio
async def test_authorized_user_is_permitted_and_processed():
    spy_adapter = SpyTelegramAdapter()
    app = create_app(
        messenger_adapter=spy_adapter,
        allowed_user_ids=["999888"]
    )

    authorized_payload = make_telegram_payload(user_id=999888, text="שלום רמ\"ד")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhook/telegram", json=authorized_payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(spy_adapter.sent_messages) == 1
    assert spy_adapter.sent_messages[0][0] == "999888"
