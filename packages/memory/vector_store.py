import hashlib
import math
import re
import uuid
import httpx
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import SemanticMemoryChunk
from packages.llm_router.vault import ConfigVault


class EmpireSemanticMemory:
    """
    Memória Vetorial de Longo Prazo (pgvector em Postgres + Motor Híbrido Cosine RAG).
    Permite que todos os departamentos partilhem contexto histórico, padrões de código
    auto-corrigidos, playbooks comerciais e diretrizes soberanas do CEO.
    """

    LOCAL_DIM = 128

    @classmethod
    def _local_ngram_embedding(cls, text: str) -> list[float]:
        vec = [0.0] * cls.LOCAL_DIM
        tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]{2,}", text.lower())
        features = list(tokens)
        for t in tokens:
            if len(t) >= 4:
                for i in range(len(t) - 2):
                    features.append(t[i : i + 3])
        if not features:
            vec[0] = 1.0
            return vec

        for feat in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % cls.LOCAL_DIM
            sign = 1.0 if (digest[4] % 2 == 0) else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    @classmethod
    async def compute_embedding(cls, db: AsyncSession, text: str) -> list[float]:
        openai_key = await ConfigVault.get_secret(db, "OPENAI_API_KEY")
        if openai_key:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {openai_key}"},
                        json={"model": "text-embedding-3-small", "input": text[:4000]},
                    )
                    if resp.status_code == 200:
                        return resp.json()["data"][0]["embedding"]
            except Exception:
                pass
        return cls._local_ngram_embedding(text)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))

    @classmethod
    async def store_memory(
        cls,
        db: AsyncSession,
        namespace: str,
        source_agent: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticMemoryChunk:
        emb = await cls.compute_embedding(db, f"{title}\n{content}")
        chunk = SemanticMemoryChunk(
            id=f"mem-{uuid.uuid4().hex[:10]}",
            namespace=namespace,
            source_agent=source_agent,
            title=title,
            content=content,
            embedding_json=emb,
            metadata_json=metadata or {},
        )
        db.add(chunk)
        await db.commit()

        await event_bus.publish(
            event_type="VECTOR_MEMORY_STORED",
            agent_slug=source_agent,
            level="INFO",
            message=f"[Memória Vetorial • {namespace}] Indexado: '{title[:70]}'",
            payload={"memory_id": chunk.id, "namespace": namespace},
        )
        return chunk

    @classmethod
    async def search_similar(
        cls,
        db: AsyncSession,
        query: str,
        namespace: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        q_emb = await cls.compute_embedding(db, query)
        stmt = select(SemanticMemoryChunk).order_by(desc(SemanticMemoryChunk.created_at)).limit(200)
        if namespace and namespace != "ALL":
            stmt = stmt.where(SemanticMemoryChunk.namespace == namespace)

        res = await db.execute(stmt)
        rows = res.scalars().all()

        scored = []
        for r in rows:
            emb = r.embedding_json or []
            if len(emb) != len(q_emb):
                emb = cls._local_ngram_embedding(f"{r.title}\n{r.content}")
                score = cls._cosine(cls._local_ngram_embedding(query), emb)
            else:
                score = cls._cosine(q_emb, emb)
            scored.append(
                {
                    "id": r.id,
                    "namespace": r.namespace,
                    "source_agent": r.source_agent,
                    "title": r.title,
                    "content": r.content,
                    "similarity": round(max(0.0, score), 4),
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
            )

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]
