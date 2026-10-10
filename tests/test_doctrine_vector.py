import pytest
from pathlib import Path
from ramad_assistant.db.repository import TaskRepository
from ramad_assistant.db.doctrine_vector import DoctrineVectorStore, chunk_doctrine_text, cosine_similarity
from ramad_assistant.db.seed_doctrine import seed_doctrine


def test_chunk_doctrine_text():
    sample_md = """# Title
## 1. ייעוד המדור
ייעוד המדור הוא מחקר ופיתוח פתרונות טכנולוגיים.
### א. עקרונות פיקודיים
דוגמא אישית ואותנטיות.
## 2. שגרות עבודה
מה שלא ביומן לא קורה.
"""
    chunks = chunk_doctrine_text(sample_md)
    assert len(chunks) == 3
    assert chunks[0]["section_title"] == "1. ייעוד המדור"
    assert "ייעוד המדור" in chunks[0]["content"]
    assert chunks[1]["section_title"] == "א. עקרונות פיקודיים"
    assert chunks[2]["section_title"] == "2. שגרות עבודה"


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == pytest.approx(1.0)
    assert cosine_similarity(v1, v3) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_seed_and_similarity_search(tmp_path):
    db_path = str(tmp_path / "test_doctrine.db")
    doc_path = tmp_path / "test_doctrine.md"
    doc_path.write_text(
        Path("doctrine.md").read_text(encoding="utf-8"),
        encoding="utf-8"
    )

    count = await seed_doctrine(
        doctrine_path=str(doc_path),
        db_url=f"sqlite:///{db_path}",
    )
    assert count > 5

    repo = TaskRepository(db_url=f"sqlite:///{db_path}")
    store = DoctrineVectorStore(repo=repo)
    query_emb = await store.generate_embedding("מה שלא ביומן לא קורה שגרות יומן")
    results = store.similarity_search(query_emb, top_k=2)

    assert len(results) == 2
    assert any("יומן" in res["content"] or "שגרות" in res["section_title"] for res in results)
