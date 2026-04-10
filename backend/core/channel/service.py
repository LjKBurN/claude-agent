"""Channel Service。

管理 Channel 生命周期，路由消息到 AgentService。
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.channel.base import ChannelAdapter
from backend.core.channel.types import ChannelMessage
from backend.core.channel.wechat import WeChatAdapter
from backend.db.database import async_session
from backend.db.models import Channel, ChannelSession

logger = logging.getLogger(__name__)


class ChannelService:
    """Channel 管理服务。

    职责：
    1. 管理 adapter 生命周期（start/stop）
    2. IM 会话 → Agent 会话映射
    3. 消息路由到 AgentService
    4. 发送者白名单
    """

    def __init__(self):
        self._adapters: dict[str, ChannelAdapter] = {}
        self._running = False

    # ==================== Channel 管理 ====================

    async def start_channel(self, channel_id: str) -> dict[str, Any]:
        """启动指定 channel。"""
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return {"success": False, "error": "Channel not registered"}

        await adapter.start()
        return {"success": True, "channel_id": channel_id}

    async def stop_channel(self, channel_id: str) -> dict[str, Any]:
        """停止指定 channel。"""
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return {"success": False, "error": "Channel not registered"}

        await adapter.stop()
        return {"success": True, "channel_id": channel_id}

    async def start_all(self) -> None:
        """启动所有已注册的 channel。"""
        for channel_id, adapter in self._adapters.items():
            try:
                await adapter.start()
                logger.info(f"Started channel: {channel_id}")
            except Exception as e:
                logger.error(f"Failed to start channel {channel_id}: {e}")

    async def stop_all(self) -> None:
        """停止所有 channel。"""
        for channel_id, adapter in self._adapters.items():
            try:
                await adapter.stop()
            except Exception as e:
                logger.error(f"Failed to stop channel {channel_id}: {e}")

    def register_adapter(self, channel_id: str, adapter: ChannelAdapter) -> None:
        """注册 adapter。"""
        self._adapters[channel_id] = adapter

    def get_adapter(self, channel_id: str) -> ChannelAdapter | None:
        """获取 adapter。"""
        return self._adapters.get(channel_id)

    # ==================== 从数据库加载 ====================

    async def load_channels(self) -> None:
        """从数据库加载所有 enabled 的 channel 并注册。"""
        async with async_session() as db:
            result = await db.execute(
                select(Channel).where(Channel.enabled)
            )
            channels = result.scalars().all()

            for channel in channels:
                try:
                    adapter = self._create_adapter(channel)
                    if adapter:
                        self.register_adapter(channel.id, adapter)
                        logger.info(f"Loaded channel: {channel.id} ({channel.platform})")
                except Exception as e:
                    logger.error(f"Failed to load channel {channel.id}: {e}")

    def _create_adapter(self, channel: Channel) -> ChannelAdapter | None:
        """根据平台创建 adapter。"""
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
        # 后续扩展飞书等
        logger.warning(f"Unknown platform: {channel.platform}")
        return None

    # ==================== 消息处理 ====================

    async def _on_message(self, channel_id: str, message: ChannelMessage) -> None:
        """收到消息的回调处理。

        流程：
        1. 白名单检查
        2. 查找/创建 IM↔Agent 会话映射
        3. 发送 typing 状态
        4. 后台调用 AgentService.chat()
        5. 将结果通过 adapter 发回
        """
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return

        # 1. 白名单检查
        async with async_session() as db:
            result = await db.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = result.scalar_one_or_none()
            if not channel:
                return

            allowed = channel.allowed_senders or []
            if allowed and message.sender_id not in allowed:
                logger.debug(
                    f"[channel:{channel_id}] Sender {message.sender_id} not in whitelist"
                )
                return

            # 2. 查找/创建会话映射
            agent_session_id = await self._get_or_create_session(
                db, channel_id, message.conversation_id
            )

        # 3. 发送 typing
        try:
            await adapter.send_typing(message.conversation_id)
        except Exception:
            pass

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
        """后台处理 agent 调用并发送回复。"""
        adapter = self._adapters.get(channel_id)
        if not adapter:
            return

        try:
            from backend.core.agent_service import agent_service

            async with async_session() as db:
                response = await agent_service.chat(
                    user_message=user_text,
                    session_id=agent_session_id,
                    db=db,
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
        db: AsyncSession,
        channel_id: str,
        im_conversation_id: str,
    ) -> str:
        """查找或创建 IM↔Agent 会话映射。

        同一个 IM 会话始终映射到同一个 agent session（一对一）。
        """
        # 查找已有映射
        result = await db.execute(
            select(ChannelSession)
            .where(ChannelSession.channel_id == channel_id)
            .where(ChannelSession.im_conversation_id == im_conversation_id)
        )
        mapping = result.scalar_one_or_none()

        if mapping:
            mapping.last_active_at = datetime.utcnow()
            await db.flush()
            return mapping.agent_session_id

        # 创建新映射
        agent_session_id = str(uuid.uuid4())
        mapping = ChannelSession(
            channel_id=channel_id,
            im_conversation_id=im_conversation_id,
            agent_session_id=agent_session_id,
            last_active_at=datetime.utcnow(),
        )
        db.add(mapping)
        await db.flush()

        logger.info(
            f"[channel:{channel_id}] New mapping: {im_conversation_id} -> {agent_session_id}"
        )
        return agent_session_id


# 全局服务实例
channel_service = ChannelService()
