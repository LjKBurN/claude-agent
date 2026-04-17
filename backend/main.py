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

    # 加载并启动 channels
    from backend.core.channel.service import channel_service
    await channel_service.load_channels()
    await channel_service.start_all()

    yield

    await channel_service.stop_all()


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
