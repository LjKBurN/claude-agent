"""工具列表 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.api.schemas.agent_config import (
    McpServerItem,
    SkillItem,
    ToolInfo,
    ToolsListResponse,
)
from backend.core.tools.registry import populate_registry
from backend.db.database import get_db
from backend.db.models.mcp_server import MCPServerModel
from backend.middleware.auth import verify_api_key

router = APIRouter()


@router.get("", response_model=ToolsListResponse)
async def list_tools(
    db=None,
    _: str = Depends(verify_api_key),
) -> ToolsListResponse:
    """列出所有可用工具（按来源分组）+ Skills + MCP Servers。"""
    # 获取 DB session（tools 端点用同步依赖风格）
    from backend.db.database import async_session
    if db is None:
        async with async_session() as session:
            return await _list_tools_inner(session)
    return await _list_tools_inner(db)


async def _list_tools_inner(db) -> ToolsListResponse:
    """内部实现。"""
    registry = populate_registry(skills=[], mcp_servers=[])
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

    # Skills 列表
    skills: list[SkillItem] = []
    try:
        from backend.core.skills.registry import skill_registry

        for skill in skill_registry.list_all():
            if skill.description:
                skills.append(
                    SkillItem(
                        name=skill.name,
                        description=skill.description,
                        source=skill.source,
                    )
                )
    except Exception:
        pass

    # MCP Servers 列表 — 从 DB 查询
    mcp_servers: list[McpServerItem] = []
    try:
        from backend.core.mcp.manager import mcp_manager

        result = await db.execute(
            select(MCPServerModel).where(MCPServerModel.enabled == True)  # noqa: E712
        )
        models = result.scalars().all()

        # 同步到 manager 以获取连接状态
        for model in models:
            if model.name not in mcp_manager._configs:
                mcp_manager.update_config(model.name, model.to_config())

        status = mcp_manager.get_configured_servers()
        for model in models:
            info = status.get(model.name, {"connected": False, "tools_count": 0})
            mcp_servers.append(
                McpServerItem(
                    name=model.name,
                    tools_count=info["tools_count"],
                    connected=info["connected"],
                )
            )
    except Exception:
        pass

    return ToolsListResponse(
        tools=tool_infos,
        builtin=builtin,
        mcp=mcp,
        skills=skills,
        mcp_servers=mcp_servers,
    )
