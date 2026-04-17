"""Agent Config 管理 API 路由。"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.agent_config import (
    AgentConfigInfo,
    AgentConfigList,
    CreateAgentConfigRequest,
    UpdateAgentConfigRequest,
)
from backend.db.database import get_db
from backend.db.models.agent_config import AgentConfigModel
from backend.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


def _model_to_info(model: AgentConfigModel) -> AgentConfigInfo:
    """将 ORM 模型转换为 API 响应模型。"""
    return AgentConfigInfo(
        id=model.id,
        name=model.name,
        description=model.description,
        model_id=model.model_id,
        max_tokens=model.max_tokens,
        builtin_tools=model.builtin_tools or [],
        include_skills=model.include_skills,
        include_mcp=model.include_mcp,
        mcp_servers=model.mcp_servers or [],
        max_iterations=model.max_iterations,
        tool_timeout=model.tool_timeout,
        auto_approve_safe=model.auto_approve_safe,
        system_prompt_overrides=model.system_prompt_overrides or {},
        avatar=model.avatar,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=AgentConfigList)
async def list_agent_configs(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> AgentConfigList:
    """列出所有 Agent 配置。"""
    # 查询总数
    count_result = await db.execute(select(func.count(AgentConfigModel.id)))
    total = count_result.scalar() or 0

    # 查询列表
    result = await db.execute(
        select(AgentConfigModel).order_by(AgentConfigModel.created_at.desc())
    )
    configs = result.scalars().all()

    return AgentConfigList(
        configs=[_model_to_info(c) for c in configs],
        total=total,
    )


@router.post("", response_model=AgentConfigInfo, status_code=201)
async def create_agent_config(
    request: CreateAgentConfigRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> AgentConfigInfo:
    """创建 Agent 配置。"""
    # 检查名称唯一性
    existing = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent '{request.name}' 已存在")

    model = AgentConfigModel(
        id=str(uuid4()),
        name=request.name,
        description=request.description,
        model_id=request.model_id,
        max_tokens=request.max_tokens,
        builtin_tools=request.builtin_tools,
        include_skills=request.include_skills,
        include_mcp=request.include_mcp,
        mcp_servers=request.mcp_servers,
        max_iterations=request.max_iterations,
        tool_timeout=request.tool_timeout,
        auto_approve_safe=request.auto_approve_safe,
        system_prompt_overrides=request.system_prompt_overrides,
        avatar=request.avatar,
    )

    db.add(model)
    await db.commit()
    await db.refresh(model)

    logger.info(f"Created agent config: {model.name} ({model.id})")
    return _model_to_info(model)


@router.get("/{config_id}", response_model=AgentConfigInfo)
async def get_agent_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> AgentConfigInfo:
    """获取 Agent 配置详情。"""
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == config_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Agent config not found")

    return _model_to_info(model)


@router.put("/{config_id}", response_model=AgentConfigInfo)
async def update_agent_config(
    config_id: str,
    request: UpdateAgentConfigRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> AgentConfigInfo:
    """更新 Agent 配置。"""
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == config_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Agent config not found")

    # 检查名称唯一性（如果修改了名称）
    if request.name is not None and request.name != model.name:
        existing = await db.execute(
            select(AgentConfigModel).where(AgentConfigModel.name == request.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail=f"Agent '{request.name}' 已存在"
            )

    # 只更新提供的字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)

    await db.commit()
    await db.refresh(model)

    logger.info(f"Updated agent config: {model.name} ({model.id})")
    return _model_to_info(model)


@router.delete("/{config_id}")
async def delete_agent_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """删除 Agent 配置。"""
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == config_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Agent config not found")

    await db.delete(model)
    await db.commit()

    logger.info(f"Deleted agent config: {model.name} ({model.id})")
    return {"status": "deleted", "id": config_id}
