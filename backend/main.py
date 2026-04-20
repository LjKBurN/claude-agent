"""FastAPI 应用入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import router
from backend.config import get_settings
from backend.db.database import init_db

# 配置日志：确保 backend.* 模块的 INFO 日志输出到终端
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    await init_db()

    # 一次性迁移：.mcp.json → DB
    await _migrate_mcp_json_to_db()

    # 加载并启动 channels
    from backend.core.channel.service import channel_service
    await channel_service.load_channels()
    await channel_service.start_all()

    yield

    await channel_service.stop_all()


async def _migrate_mcp_json_to_db() -> None:
    """将 .mcp.json 中的配置迁移到数据库（仅在 DB 为空时执行）。"""
    import json
    from pathlib import Path
    from uuid import uuid4

    from sqlalchemy import select, func
    from backend.db.database import async_session
    from backend.db.models.mcp_server import MCPServerModel

    async with async_session() as session:
        # 检查 DB 是否已有数据
        count_result = await session.execute(select(func.count(MCPServerModel.id)))
        if count_result.scalar() > 0:
            return

        # 查找 .mcp.json
        project_root = Path(__file__).resolve().parent.parent
        mcp_json = project_root / ".mcp.json"
        if not mcp_json.exists():
            return

        try:
            with open(mcp_json) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        servers = data.get("mcpServers", {})
        if not servers:
            return

        count = 0
        for name, conf in servers.items():
            if not isinstance(conf, dict):
                continue
            model = MCPServerModel(
                id=str(uuid4()),
                name=name,
                transport="http" if conf.get("url") else "stdio",
                command=conf.get("command", ""),
                args=conf.get("args", []),
                env=conf.get("env", {}),
                url=conf.get("url", ""),
                headers=conf.get("headers", {}),
                enabled=True,
                description=f"Migrated from .mcp.json",
            )
            session.add(model)
            count += 1

        await session.commit()
        if count:
            logging.getLogger(__name__).info(f"Migrated {count} MCP servers from .mcp.json to DB")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Claude Agent API",
        description="AI Agent 服务",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
