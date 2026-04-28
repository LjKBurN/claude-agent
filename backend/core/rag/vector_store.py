"""pgvector 向量存储与语义检索。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """向量检索结果。"""

    chunk_id: str
    document_id: str
    document_title: str
    content: str
    score: float
    chunk_index: int
    section_headers: list[str]
    metadata: dict


class PgVectorStore:
    """基于 pgvector 的向量存储与检索。"""

    async def store_embeddings(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        db: AsyncSession,
    ) -> None:
        """批量更新 chunks 的 embedding 列。"""
        from backend.db.models.knowledge_base import DocumentChunk

        for chunk_id, embedding in zip(chunk_ids, embeddings):
            chunk = await db.get(DocumentChunk, chunk_id)
            if chunk:
                chunk.embedding = embedding

    async def search(
        self,
        query_embedding: list[float],
        kb_ids: list[str],
        top_k: int = 5,
        db: AsyncSession | None = None,
    ) -> list[SearchResult]:
        """余弦相似度检索。

        使用 pgvector 的 <=> 操作符（余弦距离），score = 1 - distance。
        """
        if db is None:
            raise ValueError("db session is required")

        # 使用原生 SQL 进行向量检索（SQLAlchemy ORM 对 pgvector 支持有限）
        # 使用 :kb_id_0, :kb_id_1, ... 参数避免 SQL 注入
        kb_placeholders = ", ".join(f":kb_id_{i}" for i in range(len(kb_ids)))
        query_sql = text(f"""
            SELECT
                chunk.id AS chunk_id,
                chunk.document_id,
                doc.title AS document_title,
                chunk.content,
                1 - (chunk.embedding <=> :query_vec) AS score,
                chunk.chunk_index,
                chunk.section_headers,
                chunk.metadata
            FROM document_chunks chunk
            JOIN documents doc ON chunk.document_id = doc.id
            WHERE doc.knowledge_base_id IN ({kb_placeholders})
              AND chunk.embedding IS NOT NULL
            ORDER BY chunk.embedding <=> :query_vec
            LIMIT :top_k
        """)

        params: dict = {
            "query_vec": str(query_embedding),
            "top_k": top_k,
        }
        for i, kb_id in enumerate(kb_ids):
            params[f"kb_id_{i}"] = kb_id

        result = await db.execute(query_sql, params)
        rows = result.fetchall()

        return [
            SearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                content=row.content,
                score=float(row.score),
                chunk_index=row.chunk_index,
                section_headers=row.section_headers or [],
                metadata=row.metadata or {},
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_instance: PgVectorStore | None = None


def get_vector_store() -> PgVectorStore:
    """获取 PgVectorStore 单例。"""
    global _instance
    if _instance is None:
        _instance = PgVectorStore()
    return _instance
