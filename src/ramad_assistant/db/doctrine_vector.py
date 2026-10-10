"""Vector storage and chunk retrieval for Ramad command doctrine."""
import json
import math
import re
from typing import Any, Optional
import httpx

from ramad_assistant.db.repository import TaskRepository


class DoctrineVectorStore:
    def __init__(self, repo: TaskRepository, api_key: str = ""):
        self.repo = repo
        self.api_key = api_key

    def init_table(self) -> None:
        with self.repo._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_doctrine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    section_title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT,  -- JSON list of float
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.commit()

    def add_chunk(
        self,
        section_title: str,
        content: str,
        embedding: list[float],
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        embedding_json = json.dumps(embedding)
        with self.repo._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO command_doctrine (section_title, content, embedding, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (section_title, content, embedding_json, metadata_json),
            )
            conn.commit()
            return cursor.lastrowid

    def list_chunks(self) -> list[dict[str, Any]]:
        with self.repo._get_connection() as conn:
            rows = conn.execute("SELECT id, section_title, content, metadata FROM command_doctrine").fetchall()
            return [dict(r) for r in rows]

    def similarity_search(self, query_vector: list[float], top_k: int = 3) -> list[dict[str, Any]]:
        with self.repo._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, section_title, content, embedding, metadata FROM command_doctrine WHERE embedding IS NOT NULL"
            ).fetchall()

        results = []
        for r in rows:
            emb = json.loads(r["embedding"])
            score = cosine_similarity(query_vector, emb)
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            results.append({
                "id": r["id"],
                "section_title": r["section_title"],
                "content": r["content"],
                "score": score,
                "metadata": meta,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates 768-dim embedding via Gemini API if key exists, else deterministic fallback."""
        if self.api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={self.api_key}"
            payload = {
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": text}]},
            }
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    if resp.status_code == 200:
                        values = resp.json().get("embedding", {}).get("values", [])
                        if values:
                            return values
            except Exception:
                pass
        return generate_deterministic_embedding(text)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def generate_deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    """Generates a pseudo-semantic dense vector for tests and offline usage."""
    vec = [0.0] * dim
    words = re.findall(r"\w+", text.lower())
    if not words:
        return vec
    for i, word in enumerate(words):
        # hash word to several dimensions
        h = hash(word)
        idx = abs(h) % dim
        vec[idx] += 1.0
        # secondary feature
        vec[(idx * 31 + 7) % dim] += 0.5
    # Normalize to unit vector
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def chunk_doctrine_text(markdown_text: str) -> list[dict[str, str]]:
    """Chunks markdown document by headers (## and ###)."""
    chunks: list[dict[str, str]] = []
    lines = markdown_text.splitlines()

    current_title = "מבוא"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if current_lines:
                chunk_text = "\n".join(current_lines).strip()
                # If current_title is "מבוא" and chunk_text only has top-level titles, skip or include only if meaningful
                if chunk_text and not (current_title == "מבוא" and all(line_item.startswith("#") for line_item in chunk_text.splitlines())):
                    chunks.append({"section_title": current_title, "content": chunk_text})
                current_lines = []
            current_title = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text:
            chunks.append({"section_title": current_title, "content": chunk_text})

    return chunks
