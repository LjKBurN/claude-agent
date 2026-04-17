"""工具列表 API 路由。"""

from fastapi import APIRouter, Depends

from backend.api.schemas.agent_config import ToolInfo, ToolsListResponse
from backend.core.tools.registry import populate_registry
from backend.middleware.auth import verify_api_key

router = APIRouter()


@router.get("", response_model=ToolsListResponse)
async def list_tools(
    _: str = Depends(verify_api_key),
) -> ToolsListResponse:
    """列出所有可用工具（按来源分组）。

    用于 Agent 创建表单中的工具选择 UI。
    """
    registry = populate_registry(include_skills=False, include_mcp=True)
    all_tools = registry.all_tools()

    tool_infos = [
        ToolInfo(
            name=t.name,
            description=t.description,
            source=t.source,
            permission=t.permission,
        )
        for t in all_tools
    ]

    builtin = [t for t in tool_infos if t.source == "builtin"]
    mcp = [t for t in tool_infos if t.source == "mcp"]

    return ToolsListResponse(tools=tool_infos, builtin=builtin, mcp=mcp)
