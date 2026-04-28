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


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）。"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
