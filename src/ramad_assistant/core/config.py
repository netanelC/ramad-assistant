"""Application configuration."""
import os


class Settings:
    def __init__(self) -> None:
        raw_allowed = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "")
        self.allowed_telegram_user_ids: list[str] = [
            uid.strip() for uid in raw_allowed.split(",") if uid.strip()
        ]
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "placeholder-token")
        self.api_secret: str = os.getenv("API_SECRET", "dev-secret")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ramad_tasks.db")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")


def get_settings() -> Settings:
    return Settings()
