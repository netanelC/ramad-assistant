"""Abstract Messenger Adapter interface (Hexagonal architecture)."""
from abc import ABC, abstractmethod
from typing import Any

from ramad_assistant.core.models import UnifiedMessage


class IMessengerAdapter(ABC):
    @abstractmethod
    async def parse_inbound(self, payload: dict[str, Any]) -> UnifiedMessage:
        """Parses webhook payload from the messaging platform into UnifiedMessage."""
        pass

    @abstractmethod
    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Sends an outbound markdown text message to the user."""
        pass
