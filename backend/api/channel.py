"""Channel 管理 API 路由 — 通用 CRUD + 启停 + 白名单 + 关联会话。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.channel.service import channel_service
from backend.db.database import get_db
from backend.db.models import Channel, ChannelSession
from backend.middleware.auth import verify_api_key

router = APIRouter()


class CreateChannelRequest(BaseModel):
    name: str
    platform: str  # "wechat"
    config: dict = {}
    allowed_senders: list[str] = []


class UpdateSendersRequest(BaseModel):
    allowed_senders: list[str]


# ==================== CRUD ====================


@router.post("", dependencies=[Depends(verify_api_key)])
async def create_channel(
    req: CreateChannelRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建 Channel。"""
    channel = Channel(
        id=str(uuid.uuid4()),
        platform=req.platform,
        name=req.name,
        config=req.config,
        allowed_senders=req.allowed_senders,
    )
    db.add(channel)
    await db.commit()

    # 注册 adapter
    adapter = channel_service._create_adapter(channel)
    if adapter:
        channel_service.register_adapter(channel.id, adapter)

    return {
        "id": channel.id,
        "platform": channel.platform,
        "name": channel.name,
        "enabled": channel.enabled,
    }


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_channels(db: AsyncSession = Depends(get_db)):
    """列出所有 Channel。"""
    result = await db.execute(select(Channel))
    channels = result.scalars().all()
    return [
        {
            "id": c.id,
            "platform": c.platform,
            "name": c.name,
            "enabled": c.enabled,
            "allowed_senders": c.allowed_senders,
            "configured": channel_service.get_adapter(c.id).is_configured
                if channel_service.get_adapter(c.id) else False,
            "running": channel_service.get_adapter(c.id).is_running
                if channel_service.get_adapter(c.id) else False,
        }
        for c in channels
    ]


@router.get("/{channel_id}", dependencies=[Depends(verify_api_key)])
async def get_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    """获取 Channel 详情。"""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")
    adapter = channel_service.get_adapter(channel_id)
    return {
        "id": channel.id,
        "platform": channel.platform,
        "name": channel.name,
        "config": {
            k: v
            for k, v in channel.config.items()
            if k not in ("bot_token",)  # 不暴露敏感字段
        },
        "enabled": channel.enabled,
        "allowed_senders": channel.allowed_senders,
        "configured": adapter.is_configured if adapter else False,
        "running": adapter.is_running if adapter else False,
    }


@router.delete("/{channel_id}", dependencies=[Depends(verify_api_key)])
async def delete_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    """删除 Channel。"""
    await channel_service.stop_channel(channel_id)

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    await db.delete(channel)
    await db.commit()
    return {"success": True}


# ==================== 关联会话 ====================


@router.get("/{channel_id}/sessions", dependencies=[Depends(verify_api_key)])
async def list_channel_sessions(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """列出 Channel 关联的会话。"""
    result = await db.execute(
        select(ChannelSession)
        .where(ChannelSession.channel_id == channel_id)
        .order_by(ChannelSession.last_active_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "channel_id": s.channel_id,
            "im_conversation_id": s.im_conversation_id,
            "agent_session_id": s.agent_session_id,
            "context_data": s.context_data,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
        }
        for s in sessions
    ]


# ==================== 启停 ====================


@router.post("/{channel_id}/start", dependencies=[Depends(verify_api_key)])
async def start_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    """启动 Channel。"""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    # 确保 adapter 已注册
    if not channel_service.get_adapter(channel_id):
        adapter = channel_service._create_adapter(channel)
        if adapter:
            channel_service.register_adapter(channel.id, adapter)

    return await channel_service.start_channel(channel_id)


@router.post("/{channel_id}/stop", dependencies=[Depends(verify_api_key)])
async def stop_channel(channel_id: str):
    """停止 Channel。"""
    return await channel_service.stop_channel(channel_id)


# ==================== 白名单 ====================


@router.put("/{channel_id}/senders", dependencies=[Depends(verify_api_key)])
async def update_senders(
    channel_id: str,
    req: UpdateSendersRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新发送者白名单。"""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    channel.allowed_senders = req.allowed_senders
    await db.commit()
    return {"success": True, "allowed_senders": req.allowed_senders}
