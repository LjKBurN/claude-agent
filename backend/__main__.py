"""模块入口，支持 python -m backend 启动。"""

import uvicorn

from backend.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
