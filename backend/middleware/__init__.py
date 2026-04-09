"""中间件模块。"""

from backend.middleware.auth import verify_api_key

__all__ = ["verify_api_key"]
