"""Entrypoint script for running and seeding the application in production or local environments."""
import asyncio
import os
import uvicorn
from pathlib import Path

from ramad_assistant.core.config import get_settings
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.seed_doctrine import seed_doctrine
from ramad_assistant.gateway.app import create_app


def init_and_seed() -> None:
    settings = get_settings()
    repo = TaskRepository(db_url=settings.database_url)
    repo.init_db()

    # Seed doctrine if doctrine.md is present
    doctrine_path = Path("doctrine.md")
    if doctrine_path.exists():
        print("🌱 Seeding doctrine vector store...")
        try:
            asyncio.run(
                seed_doctrine(
                    doctrine_path=str(doctrine_path),
                    db_url=settings.database_url,
                    gemini_api_key=settings.gemini_api_key,
                )
            )
            print("✅ Doctrine seeded successfully.")
        except Exception as e:
            print(f"⚠️ Notice: Doctrine seeding encountered: {e}")


def main() -> None:
    init_and_seed()
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Starting Ramad Command Assistant Gateway on {host}:{port}")
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
