"""MCP Server 管理 API 路由。"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.mcp_server import (
    CreateMCPServerRequest,
    MCPServerInfo,
    MCPServerList,
    MCPServerStatusInfo,
    UpdateMCPServerRequest,
)
from backend.core.mcp.manager import mcp_manager
from backend.db.database import get_db
from backend.db.models.mcp_server import MCPServerModel
from backend.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


def _model_to_info(model: MCPServerModel) -> MCPServerInfo:
    """将 ORM 模型转换为 API 响应模型。"""
    return MCPServerInfo(
        id=model.id,
        name=model.name,
        transport=model.transport,
        command=model.command or "",
        args=model.args or [],
        env=model.env or {},
        url=model.url or "",
        headers=model.headers or {},
        enabled=model.enabled,
        description=model.description or "",
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


async def _get_model_or_404(server_id: str, db: AsyncSession) -> MCPServerModel:
    """按 ID 查找模型，不存在则 404。"""
    result = await db.execute(
        select(MCPServerModel).where(MCPServerModel.id == server_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return model


# ==================== CRUD ====================


@router.get("", response_model=MCPServerList)
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MCPServerList:
    """列出所有 MCP Server 配置。"""
    count_result = await db.execute(select(func.count(MCPServerModel.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(MCPServerModel).order_by(MCPServerModel.created_at.desc())
    )
    servers = result.scalars().all()

    return MCPServerList(
        servers=[_model_to_info(s) for s in servers],
        total=total,
    )


@router.post("", response_model=MCPServerInfo, status_code=201)
async def create_mcp_server(
    request: CreateMCPServerRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MCPServerInfo:
    """创建 MCP Server 配置。"""
    # 检查名称唯一性
    existing = await db.execute(
        select(MCPServerModel).where(MCPServerModel.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"MCP Server '{request.name}' 已存在")

    model = MCPServerModel(
        id=str(uuid4()),
        name=request.name,
        transport=request.transport,
        command=request.command,
        args=request.args,
        env=request.env,
        url=request.url,
        headers=request.headers,
        enabled=request.enabled,
        description=request.description,
    )

    db.add(model)
    await db.commit()
    await db.refresh(model)

    # 同步到 MCPManager
    mcp_manager.update_config(model.name, model.to_config())

    logger.info(f"Created MCP server: {model.name} ({model.id})")
    return _model_to_info(model)


@router.get("/{server_id}", response_model=MCPServerInfo)
async def get_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MCPServerInfo:
    """获取 MCP Server 配置详情。"""
    model = await _get_model_or_404(server_id, db)
    return _model_to_info(model)


@router.put("/{server_id}", response_model=MCPServerInfo)
async def update_mcp_server(
    server_id: str,
    request: UpdateMCPServerRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MCPServerInfo:
    """更新 MCP Server 配置。"""
    model = await _get_model_or_404(server_id, db)

    old_name = model.name

    # 检查名称唯一性（如果修改了名称）
    if request.name is not None and request.name != model.name:
        existing = await db.execute(
            select(MCPServerModel).where(MCPServerModel.name == request.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"MCP Server '{request.name}' 已存在"
            )

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)

    await db.commit()
    await db.refresh(model)

    # 同步到 MCPManager：名称变更时移除旧配置
    if old_name != model.name:
        await mcp_manager.remove_server(old_name)

    # 更新配置（断开已有连接，需要手动 reconnect）
    mcp_manager.update_config(model.name, model.to_config())

    logger.info(f"Updated MCP server: {model.name} ({model.id})")
    return _model_to_info(model)


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """删除 MCP Server 配置。"""
    model = await _get_model_or_404(server_id, db)

    # 断开连接 + 移除配置
    await mcp_manager.remove_server(model.name)

    await db.delete(model)
    await db.commit()

    logger.info(f"Deleted MCP server: {model.name} ({model.id})")
    return {"status": "deleted", "id": server_id}


# ==================== 连接控制 ====================


@router.post("/{server_id}/connect")
async def connect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """连接 MCP Server。"""
    model = await _get_model_or_404(server_id, db)

    # 确保配置已同步
    mcp_manager.update_config(model.name, model.to_config())

    success = await mcp_manager.connect_server(model.name)
    if not success:
        details = mcp_manager.get_server_details(model.name)
        error = details.get("error", "Unknown error") if details else "Unknown error"
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect MCP server '{model.name}': {error}",
        )

    return {"status": "connected", "name": model.name}


@router.post("/{server_id}/disconnect")
async def disconnect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """断开 MCP Server。"""
    model = await _get_model_or_404(server_id, db)
    await mcp_manager.disconnect_server(model.name)
    return {"status": "disconnected", "name": model.name}


# ==================== 状态查询 ====================


@router.get("/{server_id}/status", response_model=MCPServerStatusInfo)
async def get_mcp_server_status(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> MCPServerStatusInfo:
    """获取 MCP Server 实时状态（工具/资源/提示词）。"""
    model = await _get_model_or_404(server_id, db)

    details = mcp_manager.get_server_details(model.name)
    if not details:
        return MCPServerStatusInfo(name=model.name, connected=False)

    from backend.api.schemas.mcp_server import MCPToolInfo, MCPResourceInfo, MCPPromptInfo

    return MCPServerStatusInfo(
        name=details["name"],
        connected=details["connected"],
        error=details.get("error"),
        tools=[MCPToolInfo(**t) for t in details.get("tools", [])],
        resources=[MCPResourceInfo(**r) for r in details.get("resources", [])],
        prompts=[MCPPromptInfo(**p) for p in details.get("prompts", [])],
    )
