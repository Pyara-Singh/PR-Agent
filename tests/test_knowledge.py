import pytest

from proofmerge.knowledge import EMBEDDING_DIMENSIONS, NullKnowledgeStore, deterministic_embedding


def test_deterministic_embedding_is_stable_and_normalized() -> None:
    first = deterministic_embedding("ADR: webhook requests must be idempotent")
    second = deterministic_embedding("ADR: webhook requests must be idempotent")
    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert sum(value * value for value in first) == pytest.approx(1.0)


async def test_null_knowledge_store_is_a_safe_read_fallback() -> None:
    assert await NullKnowledgeStore().search("anything") == []
