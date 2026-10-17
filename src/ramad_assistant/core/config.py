"""Application configuration."""
import os


class Settings:
    def __init__(self) -> None:
        self.api_secret: str = os.getenv("API_SECRET", "dev-secret")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ramad_tasks.db")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")


def get_settings() -> Settings:
    return Settings()
