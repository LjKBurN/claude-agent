"""pgvector 向量存储与 Hybrid 检索（向量 + BM25）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """检索结果。"""

    chunk_id: str
    document_id: str
    document_title: str
    content: str
    score: float
    chunk_index: int
    section_headers: list[str]
    metadata: dict


class PgVectorStore:
    """基于 pgvector 的向量存储与 Hybrid 检索。"""

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
        query_text: str | None = None,
    ) -> list[SearchResult]:
        """检索：Hybrid（向量 + BM25）或纯向量。

        Args:
            query_embedding: 查询向量。
            kb_ids: 知识库 ID 列表。
            top_k: 返回结果数。
            db: 数据库会话。
            query_text: 原始查询文本。提供时启用 Hybrid Search，
                        为 None 时回退到纯向量检索。
        """
        if db is None:
            raise ValueError("db session is required")

        if query_text:
            return await self._hybrid_search(query_embedding, query_text, kb_ids, top_k, db)
        return await self._vector_search_full(query_embedding, kb_ids, top_k, db)

    # ==================== Hybrid Search ====================

    async def _hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        kb_ids: list[str],
        top_k: int,
        db: AsyncSession,
    ) -> list[SearchResult]:
        """向量 + BM25 双路检索 → RRF 融合 → 返回 top_k 结果。"""
        # 两路各取 top_k * 2 候选，扩大召回池
        candidate_count = top_k * 2

        vector_results = await self._vector_search_ranks(
            query_embedding, kb_ids, candidate_count, db,
        )
        bm25_results = await self._bm25_search_ranks(
            query_text, kb_ids, candidate_count, db,
        )

        # RRF 融合
        fused_ids = self._rrf_fuse(vector_results, bm25_results)[:top_k]

        if not fused_ids:
            return []

        return await self._fetch_chunks_by_ids(fused_ids, db)

    # ==================== 向量检索 ====================

    async def _vector_search_full(
        self,
        query_embedding: list[float],
        kb_ids: list[str],
        top_k: int,
        db: AsyncSession,
    ) -> list[SearchResult]:
        """纯向量检索，返回完整 SearchResult。"""
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

        params: dict = {"query_vec": str(query_embedding), "top_k": top_k}
        for i, kb_id in enumerate(kb_ids):
            params[f"kb_id_{i}"] = kb_id

        result = await db.execute(query_sql, params)
        return self._rows_to_results(result.fetchall())

    async def _vector_search_ranks(
        self,
        query_embedding: list[float],
        kb_ids: list[str],
        limit: int,
        db: AsyncSession,
    ) -> list[tuple[str, int]]:
        """向量检索，返回 (chunk_id, rank) 列表。rank 从 1 开始。"""
        kb_placeholders = ", ".join(f":kb_id_{i}" for i in range(len(kb_ids)))
        query_sql = text(f"""
            SELECT chunk.id AS chunk_id
            FROM document_chunks chunk
            JOIN documents doc ON chunk.document_id = doc.id
            WHERE doc.knowledge_base_id IN ({kb_placeholders})
              AND chunk.embedding IS NOT NULL
            ORDER BY chunk.embedding <=> :query_vec
            LIMIT :limit
        """)

        params: dict = {"query_vec": str(query_embedding), "limit": limit}
        for i, kb_id in enumerate(kb_ids):
            params[f"kb_id_{i}"] = kb_id

        result = await db.execute(query_sql, params)
        return [(row.chunk_id, rank) for rank, row in enumerate(result.fetchall(), 1)]

    # ==================== BM25 检索 ====================

    async def _bm25_search_ranks(
        self,
        query_text: str,
        kb_ids: list[str],
        limit: int,
        db: AsyncSession,
    ) -> list[tuple[str, int]]:
        """BM25 全文检索，返回 (chunk_id, rank) 列表。rank 从 1 开始。"""
        # jieba 中文分词后搜索（与入库时一致的分词策略）
        import jieba
        segmented_query = " ".join(jieba.cut(query_text))

        kb_placeholders = ", ".join(f":kb_id_{i}" for i in range(len(kb_ids)))
        # 用 OR 连接词元（替代 plainto_tsquery 的 AND），任意词命中即可得分
        query_sql = text(f"""
            SELECT chunk.id AS chunk_id
            FROM document_chunks chunk
            JOIN documents doc ON chunk.document_id = doc.id,
                 CAST(replace(
                     CAST(plainto_tsquery('simple', :query_text) AS text),
                     '&', '|'
                 ) AS tsquery) AS query
            WHERE chunk.content_tsvector @@ query
              AND doc.knowledge_base_id IN ({kb_placeholders})
            ORDER BY ts_rank_cd(chunk.content_tsvector, query) DESC
            LIMIT :limit
        """)

        params: dict = {"query_text": segmented_query, "limit": limit}
        for i, kb_id in enumerate(kb_ids):
            params[f"kb_id_{i}"] = kb_id

        result = await db.execute(query_sql, params)
        return [(row.chunk_id, rank) for rank, row in enumerate(result.fetchall(), 1)]

    # ==================== RRF 融合 ====================

    @staticmethod
    def _rrf_fuse(
        vector_results: list[tuple[str, int]],
        bm25_results: list[tuple[str, int]],
        k: int = 60,
    ) -> list[str]:
        """Reciprocal Rank Fusion：融合两路检索结果。

        Args:
            vector_results: (chunk_id, rank) 向量检索排名。
            bm25_results: (chunk_id, rank) BM25 检索排名。
            k: RRF 常数，默认 60（业界常用值）。

        Returns:
            按 RRF 分数降序排列的 chunk_id 列表。
        """
        scores: dict[str, float] = {}
        for chunk_id, rank in vector_results:
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        for chunk_id, rank in bm25_results:
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return sorted(scores, key=scores.get, reverse=True)  # type: ignore[arg-type]

    # ==================== 按 ID 批量查询 ====================

    async def _fetch_chunks_by_ids(
        self,
        chunk_ids: list[str],
        db: AsyncSession,
    ) -> list[SearchResult]:
        """根据 chunk_id 列表查询完整数据，保持列表顺序。"""
        if not chunk_ids:
            return []

        id_placeholders = ", ".join(f":cid_{i}" for i in range(len(chunk_ids)))
        query_sql = text(f"""
            SELECT
                chunk.id AS chunk_id,
                chunk.document_id,
                doc.title AS document_title,
                chunk.content,
                0.0 AS score,
                chunk.chunk_index,
                chunk.section_headers,
                chunk.metadata
            FROM document_chunks chunk
            JOIN documents doc ON chunk.document_id = doc.id
            WHERE chunk.id IN ({id_placeholders})
        """)

        params: dict = {}
        for i, cid in enumerate(chunk_ids):
            params[f"cid_{i}"] = cid

        result = await db.execute(query_sql, params)
        rows = result.fetchall()

        # 按 chunk_ids 顺序排列（RRF 融合后的排名）
        row_map = {row.chunk_id: row for row in rows}
        return [
            SearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                content=row.content,
                score=0.0,
                chunk_index=row.chunk_index,
                section_headers=row.section_headers or [],
                metadata=row.metadata or {},
            )
            for cid in chunk_ids
            if (row := row_map.get(cid))
        ]

    # ==================== 工具方法 ====================

    @staticmethod
    def _rows_to_results(rows) -> list[SearchResult]:
        """将 SQL 查询行转换为 SearchResult 列表。"""
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
