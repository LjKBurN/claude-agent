"""数据库连接和初始化。"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 基类。"""
    pass


# 创建异步引擎
engine = create_async_engine(
    get_settings().database_url,
    echo=get_settings().debug,
)

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _is_postgresql() -> bool:
    """检查当前数据库是否为 PostgreSQL。"""
    return "postgresql" in get_settings().database_url


async def init_db():
    """初始化数据库（创建表）。"""
    # 确保所有 ORM 模型已注册到 Base.metadata
    import backend.db.models  # noqa: F401

    async with engine.begin() as conn:
        # PostgreSQL: 创建 pgvector 扩展（需在创建表之前）
        if _is_postgresql():
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        await conn.run_sync(Base.metadata.create_all)

        # PostgreSQL: 创建 HNSW 向量索引
        if _is_postgresql():
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
            ))

            # Hybrid Search: tsvector 全文检索列 + GIN 索引
            await conn.execute(text(
                "ALTER TABLE document_chunks "
                "ADD COLUMN IF NOT EXISTS content_tsvector tsvector"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_chunks_tsvector "
                "ON document_chunks USING gin(content_tsvector)"
            ))
            # 删除旧的 PL/pgSQL 触发器（改用应用层 jieba 分词生成 tsvector）
            await conn.execute(text(
                "DROP TRIGGER IF EXISTS document_chunks_tsvector_update "
                "ON document_chunks"
            ))
            await conn.execute(text(
                "DROP FUNCTION IF EXISTS document_chunks_tsvector_trigger()"
            ))

    # 回填已有数据（使用 jieba 中文分词后生成 tsvector）
    if _is_postgresql():
        await _backfill_tsvector()


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）。"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _backfill_tsvector() -> None:
    """用 jieba 分词回填已有 chunk 的 content_tsvector。"""
    import jieba

    async with async_session() as db:
        # 查找需要回填的 chunk
        result = await db.execute(text(
            "SELECT id, content FROM document_chunks WHERE content_tsvector IS NULL"
        ))
        rows = result.fetchall()
        if not rows:
            return

        logger.info("Backfilling tsvector for %d chunks with jieba segmentation", len(rows))
        for row in rows:
            segmented = " ".join(jieba.cut(row.content))
            await db.execute(text(
                "UPDATE document_chunks SET content_tsvector = "
                "to_tsvector('simple', :segmented) WHERE id = :id"
            ), {"segmented": segmented, "id": row.id})
        await db.commit()
        logger.info("Tsvector backfill complete")
