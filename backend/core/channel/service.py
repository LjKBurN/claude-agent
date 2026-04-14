"""ChannelService — Adapter 生命周期 + 消息路由 + 会话映射。"""

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from backend.core.channel.types import ChannelMessage
from backend.core.channel.wechat import WeChatAdapter
from backend.db.database import async_session
from backend.db.models import Channel, ChannelSession, Session

logger = logging.getLogger(__name__)


class ChannelService:
    """Channel 管理服务。

    职责：
    1. 管理 adapter 生命周期（register/start/stop）
    2. 消息路由（白名单 → 会话映射 → Agent 调用）
    3. IM ↔ Agent 会话映射
    """

    def __init__(self):
        self._adapters: dict = {}

    # ==================== Adapter 管理 ====================

    def register_adapter(self, channel_id: str, adapter) -> None:
        self._adapters[channel_id] = adapter

    def get_adapter(self, channel_id: str):
        return self._adapters.get(channel_id)

    def _create_adapter(self, channel):
        config = {
            **channel.config,
            "allowed_senders": channel.allowed_senders or [],
        }
        if channel.platform == "wechat":
            return WeChatAdapter(
                channel_id=channel.id,
                config=config,
                on_message=self._on_message,
            )
        logger.warning(f"Unknown platform: {channel.platform}")
        return None

    # ==================== 启停 ====================

    async def start_channel(self, channel_id: str) -> dict:
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return {"success": False, "error": "Adapter not registered"}
        await adapter.start()
        return {"success": True, "channel_id": channel_id}

    async def stop_channel(self, channel_id: str) -> dict:
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return {"success": False, "error": "Adapter not registered"}
        await adapter.stop()
        return {"success": True, "channel_id": channel_id}

    async def start_all(self) -> None:
        for channel_id, adapter in self._adapters.items():
            try:
                await adapter.start()
                logger.info(f"Started channel: {channel_id}")
            except Exception as e:
                logger.error(f"Failed to start channel {channel_id}: {e}")

    async def stop_all(self) -> None:
        for channel_id, adapter in self._adapters.items():
            try:
                await adapter.stop()
            except Exception as e:
                logger.error(f"Failed to stop channel {channel_id}: {e}")

    # ==================== 从 DB 加载 ====================

    async def load_channels(self) -> None:
        async with async_session() as db:
            result = await db.execute(select(Channel).where(Channel.enabled))
            channels = result.scalars().all()

            for channel in channels:
                try:
                    adapter = self._create_adapter(channel)
                    if adapter:
                        self.register_adapter(channel.id, adapter)
                        logger.info(f"Loaded channel: {channel.id} ({channel.platform})")
                except Exception as e:
                    logger.error(f"Failed to load channel {channel.id}: {e}")

    # ==================== 消息路由 ====================

    async def _on_message(self, channel_id: str, message: ChannelMessage) -> None:
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return

        async with async_session() as db:
            # 1. 白名单检查
            result = await db.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = result.scalar_one_or_none()
            if not channel:
                return

            allowed = channel.allowed_senders or []
            if allowed and message.sender_id not in allowed:
                logger.info(
                    f"[channel:{channel_id}] BLOCKED sender={message.sender_id}, "
                    f"allowed={allowed}"
                )
                return

            logger.info(
                f"[channel:{channel_id}] ACCEPTED sender={message.sender_id}, "
                f"conv={message.conversation_id}, text={message.text[:50]}"
            )

            # 2. 查找/创建会话映射
            agent_session_id = await self._get_or_create_session(
                db, channel_id, message.conversation_id
            )

        # 3. 发送 typing
        try:
            await adapter.send_typing(message.conversation_id)
        except Exception as e:
            logger.warning(f"[channel:{channel_id}] send_typing failed: {e}")

        # 4 & 5. 后台处理并回复
        asyncio.create_task(
            self._process_and_reply(
                channel_id=channel_id,
                conversation_id=message.conversation_id,
                agent_session_id=agent_session_id,
                user_text=message.text,
            )
        )

    async def _process_and_reply(
        self,
        channel_id: str,
        conversation_id: str,
        agent_session_id: str,
        user_text: str,
    ) -> None:
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return

        try:
            from backend.core.agent_service import agent_service

            logger.info(
                f"[channel:{channel_id}] Calling agent: "
                f"session={agent_session_id[:12]}..., text={user_text[:50]}"
            )

            async with async_session() as db:
                response = await agent_service.chat(
                    user_message=user_text,
                    session_id=agent_session_id,
                    db=db,
                )

            logger.info(
                f"[channel:{channel_id}] Agent replied: "
                f"len={len(response.message) if response.message else 0}"
            )

            reply_text = response.message
            if reply_text:
                await adapter.send_message(conversation_id, reply_text)

        except Exception as e:
            logger.error(
                f"[channel:{channel_id}] Process error: {e}", exc_info=True
            )
            try:
                await adapter.send_message(
                    conversation_id, f"[Error] 处理失败: {str(e)[:200]}"
                )
            except Exception:
                pass

    async def _get_or_create_session(
        self,
        db,
        channel_id: str,
        im_conversation_id: str,
    ) -> str:
        result = await db.execute(
            select(ChannelSession)
            .where(ChannelSession.channel_id == channel_id)
            .where(ChannelSession.im_conversation_id == im_conversation_id)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            mapping.last_active_at = datetime.utcnow()
            await db.commit()
            return mapping.agent_session_id

        agent_session_id = str(uuid.uuid4())
        # 同时创建 Session 记录，确保 agent_service.chat() 能找到该会话
        db.add(Session(id=agent_session_id))
        mapping = ChannelSession(
            channel_id=channel_id,
            im_conversation_id=im_conversation_id,
            agent_session_id=agent_session_id,
            last_active_at=datetime.utcnow(),
        )
        db.add(mapping)
        await db.commit()

        logger.info(
            f"[channel:{channel_id}] New mapping: {im_conversation_id} -> {agent_session_id}"
        )
        return agent_session_id


# 全局服务实例
channel_service = ChannelService()
