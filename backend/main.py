"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import router
from backend.config import get_settings
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时
    await init_db()

    # 加载并启动 channels
    from backend.core.channel.service import channel_service
    await channel_service.load_channels()
    await channel_service.start_all()

    yield

    # 关闭时停止所有 channels
    await channel_service.stop_all()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    settings = get_settings()

    app = FastAPI(
        title="Claude Agent API",
        description="企业级 AI Agent 服务",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(router, prefix="/api")

    # 健康检查（无需认证）
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
