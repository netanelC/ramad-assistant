"""Script to seed doctrine.md into command_doctrine vector storage."""
import asyncio
import os
from pathlib import Path
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore, chunk_doctrine_text


async def seed_doctrine(
    doctrine_path: str = "doctrine.md",
    db_url: str = "sqlite:///./ramad_tasks.db",
    gemini_api_key: str = "",
) -> int:
    repo = TaskRepository(db_url=db_url)
    repo.init_db()

    vector_store = DoctrineVectorStore(repo=repo, api_key=gemini_api_key)
    vector_store.init_table()

    path = Path(doctrine_path)
    if not path.exists():
        raise FileNotFoundError(f"Doctrine file not found at {doctrine_path}")

    text = path.read_text(encoding="utf-8")
    chunks = chunk_doctrine_text(text)

    inserted_count = 0
    for chunk in chunks:
        emb = await vector_store.generate_embedding(chunk["content"])
        vector_store.add_chunk(
            section_title=chunk["section_title"],
            content=chunk["content"],
            embedding=emb,
            metadata={"source": "doctrine.md"},
        )
        inserted_count += 1

    return inserted_count


if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY", "")
    count = asyncio.run(seed_doctrine(gemini_api_key=api_key))
    print(f"Successfully seeded {count} doctrine chunks.")
