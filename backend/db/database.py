"""数据库连接和初始化。"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


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
    """初始化数据库（创建表）。"""
    # 确保数据目录存在
    db_path = Path("./data")
    db_path.mkdir(exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）。"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
