import hashlib
import math
import re
import uuid
from typing import Protocol

import httpx

from proofmerge.config import Settings

EMBEDDING_DIMENSIONS = 384


def deterministic_embedding(text: str) -> list[float]:
    """Create a local, stable embedding for development and offline indexing."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"[a-z0-9_./-]+", text.lower())[:20_000]:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class KnowledgeStore(Protocol):
    async def search(self, query: str, limit: int = 4) -> list[dict]: ...

    async def upsert(self, key: str, title: str, content: str, kind: str) -> None: ...


class NullKnowledgeStore:
    async def search(self, query: str, limit: int = 4) -> list[dict]:
        del query, limit
        return []

    async def upsert(self, key: str, title: str, content: str, kind: str) -> None:
        del key, title, content, kind
        raise RuntimeError("Set PROOFMERGE_QDRANT_URL before indexing project knowledge")


class QdrantKnowledgeStore:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.qdrant_url.rstrip("/")
        self.collection = settings.qdrant_collection

    async def ensure_collection(self) -> None:
        payload = {"vectors": {"size": EMBEDDING_DIMENSIONS, "distance": "Cosine"}}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.put(
                f"{self.base_url}/collections/{self.collection}", json=payload
            )
            if response.status_code not in {200, 201, 409}:
                response.raise_for_status()

    async def upsert(self, key: str, title: str, content: str, kind: str) -> None:
        await self.ensure_collection()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        payload = {
            "points": [
                {
                    "id": point_id,
                    "vector": deterministic_embedding(f"{title}\n{content}"),
                    "payload": {
                        "key": key,
                        "title": title,
                        "kind": kind,
                        "content": content[:30_000],
                    },
                }
            ]
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                f"{self.base_url}/collections/{self.collection}/points?wait=true",
                json=payload,
            )
            response.raise_for_status()

    async def search(self, query: str, limit: int = 4) -> list[dict]:
        payload = {
            "query": deterministic_embedding(query),
            "limit": limit,
            "with_payload": True,
            "score_threshold": 0.12,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/collections/{self.collection}/points/query",
                    json=payload,
                )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                points = response.json().get("result", {}).get("points", [])
        except httpx.HTTPError:
            return []
        return [
            {"score": point.get("score", 0), **(point.get("payload") or {})} for point in points
        ]


def build_knowledge_store(settings: Settings) -> KnowledgeStore:
    if settings.qdrant_url:
        return QdrantKnowledgeStore(settings)
    return NullKnowledgeStore()
