"""Channel 管理 API 路由。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.channel.service import channel_service
from backend.core.channel.wechat import WeChatAdapter
from backend.db.database import get_db
from backend.db.models import Channel
from backend.middleware.auth import verify_api_key

router = APIRouter()


# ==================== Schemas ====================


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
    if req.platform not in ("wechat",):
        raise HTTPException(400, f"Unsupported platform: {req.platform}")

    channel = Channel(
        id=str(uuid.uuid4()),
        platform=req.platform,
        name=req.name,
        config=req.config,
        allowed_senders=req.allowed_senders,
    )
    db.add(channel)
    await db.flush()

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
    await db.flush()
    return {"success": True}


# ==================== 启停 ====================


@router.post("/{channel_id}/start", dependencies=[Depends(verify_api_key)])
async def start_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    """启动 Channel。"""
    # 检查是否有 token
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    if channel.platform == "wechat" and not channel.config.get("bot_token"):
        raise HTTPException(400, "WeChat channel requires bot_token. Login first.")

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
    await db.flush()
    return {"success": True, "allowed_senders": req.allowed_senders}


# ==================== 微信登录 ====================


@router.post("/wechat/{channel_id}/qrcode", dependencies=[Depends(verify_api_key)])
async def wechat_qrcode(channel_id: str, db: AsyncSession = Depends(get_db)):
    """获取微信登录二维码。"""
    adapter = channel_service.get_adapter(channel_id)
    if not adapter or not isinstance(adapter, WeChatAdapter):
        raise HTTPException(404, "WeChat adapter not found")

    try:
        result = await adapter.request_qrcode()
        return result
    except Exception as e:
        raise HTTPException(500, f"Failed to get QR code: {e}")


@router.get("/wechat/{channel_id}/status", dependencies=[Depends(verify_api_key)])
async def wechat_login_status(
    channel_id: str,
    qrcode: str,
    db: AsyncSession = Depends(get_db),
):
    """轮询微信扫码状态。"""
    adapter = channel_service.get_adapter(channel_id)
    if not adapter or not isinstance(adapter, WeChatAdapter):
        raise HTTPException(404, "WeChat adapter not found")

    result = await adapter.check_login_status(qrcode)

    # 登录成功时保存 token 到数据库
    if result.get("status") == "confirmed":
        channel_result = await db.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = channel_result.scalar_one_or_none()
        if channel:
            channel.config.update({
                "bot_token": adapter.bot_token,
                "ilink_bot_id": adapter.ilink_bot_id,
                "ilink_user_id": adapter.ilink_user_id,
            })
            await db.flush()

    return result
