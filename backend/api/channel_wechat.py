"""微信 Channel 特定 API 路由 — QR 登录。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.channel.service import channel_service
from backend.core.channel.wechat import WeChatAdapter
from backend.db.database import get_db
from backend.db.models import Channel
from backend.middleware.auth import verify_api_key

router = APIRouter()

logger = logging.getLogger(__name__)

async def _ensure_wechat_adapter(channel_id: str, db: AsyncSession) -> WeChatAdapter:
    """确保 adapter 已注册，不存在则从 DB 创建。"""
    adapter = channel_service.get_adapter(channel_id)
    if adapter and isinstance(adapter, WeChatAdapter):
        return adapter

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel or channel.platform != "wechat":
        raise HTTPException(404, "WeChat channel not found")

    adapter = channel_service._create_adapter(channel)
    if not adapter:
        raise HTTPException(500, "Failed to create adapter")

    channel_service.register_adapter(channel.id, adapter)
    return adapter


@router.post(
    "/wechat/{channel_id}/qrcode",
    dependencies=[Depends(verify_api_key)],
)
async def wechat_qrcode(channel_id: str, db: AsyncSession = Depends(get_db)):
    """获取微信登录二维码。"""
    adapter = await _ensure_wechat_adapter(channel_id, db)
    try:
        return await adapter.request_qrcode()
    except Exception as e:
        raise HTTPException(500, f"Failed to get QR code: {e}")


@router.get(
    "/wechat/{channel_id}/status",
    dependencies=[Depends(verify_api_key)],
)
async def wechat_login_status(
    channel_id: str,
    qrcode: str,
    db: AsyncSession = Depends(get_db),
):
    """轮询微信扫码状态。"""
    logger.info(f"[wechat-login] Hit status endpoint: channel={channel_id}, qrcode={qrcode[:12]}...")
    adapter = await _ensure_wechat_adapter(channel_id, db)
    result = await adapter.check_login_status(qrcode)

    print(111111, result)
    logger.debug(
        f"[wechat-login:{channel_id}] status={result.get('status')}, "
        f"has_token={'yes' if result.get('bot_token') else 'no'}, "
        f"keys={list(result.keys())}"
    )

    # 登录成功时保存凭据到数据库
    if result.get("status") == "confirmed":
        ch_result = await db.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = ch_result.scalar_one_or_none()
        if channel:
            # 必须赋值新 dict，SQLAlchemy JSON 列不追踪 .update() 原地修改
            channel.config = {
                **channel.config,
                "bot_token": result.get("bot_token", ""),
                "ilink_bot_id": result.get("ilink_bot_id", ""),
                "ilink_user_id": result.get("ilink_user_id", ""),
            }
            # 同步更新 adapter 内存中的 token
            adapter.bot_token = result.get("bot_token", "")
            adapter.ilink_bot_id = result.get("ilink_bot_id", "")
            adapter.ilink_user_id = result.get("ilink_user_id", "")
            await db.commit()
            logger.info(
                f"[wechat-login:{channel_id}] Credentials saved to DB: "
                f"bot_token={result.get('bot_token', '')[:8]}..."
            )

    return result
