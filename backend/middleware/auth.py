"""API Key 认证中间件。"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from backend.config import get_settings, Settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    验证 API Key。

    Args:
        request: 请求对象
        api_key: 请求头中的 API Key
        settings: 应用配置

    Returns:
        验证通过的 API Key

    Raises:
        HTTPException: API Key 无效时
    """
    # 健康检查和文档不需要认证
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return ""

    if not settings.api_key:
        # 未配置 API Key 时跳过验证（开发环境）
        return ""

    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
