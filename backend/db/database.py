"""数据库连接和初始化。"""

import logging
from pathlib import Path

from sqlalchemy import inspect, text
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


async def init_db():
    """初始化数据库（创建表 + 补齐已有表的新列）。"""
    # 确保所有 ORM 模型已注册到 Base.metadata
    import backend.db.models  # noqa: F401

    # 确保数据目录存在
    db_path = Path("./data")
    db_path.mkdir(exist_ok=True)

    async with engine.begin() as conn:
        # 1. 创建不存在的表
        await conn.run_sync(Base.metadata.create_all)

        # 2. 为已有表补齐 ORM 中定义但 DB 中缺失的列
        def _migrate(sync_conn):
            db_tables = inspect(sync_conn).get_table_names()
            for table in Base.metadata.sorted_tables:
                if table.name not in db_tables:
                    continue
                existing = {col["name"] for col in inspect(sync_conn).get_columns(table.name)}
                for column in table.columns:
                    if column.name not in existing:
                        col_type = column.type.compile(sync_conn.dialect)
                        nullable = "" if column.nullable else " NOT NULL"
                        default = ""
                        if column.server_default is not None:
                            default = f" DEFAULT {column.server_default.arg.text}"
                        sql = (
                            f"ALTER TABLE {table.name} "
                            f"ADD COLUMN {column.name} {col_type}{nullable}{default}"
                        )
                        logger.info("Auto-migrate: %s", sql)
                        sync_conn.execute(text(sql))

        await conn.run_sync(_migrate)


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）。"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
