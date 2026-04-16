"""ChannelService — Adapter 生命周期 + 消息路由 + 会话映射。"""

import asyncio
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from backend.api.schemas.chat import ChatResponse
from backend.core.channel.types import ChannelMessage
from backend.core.channel.wechat import WeChatAdapter
from backend.db.database import async_session
from backend.db.models import Channel, ChannelSession, Session

logger = logging.getLogger(__name__)

# 微信消息最大长度（超出时分段发送）
MAX_MESSAGE_LENGTH = 3500
TOOL_OUTPUT_PREVIEW = 500


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
                f"len={len(response.message) if response.message else 0}, "
                f"tools={len(response.tool_calls)}, "
                f"approval={response.needs_approval}"
            )

            # 组装回复：正文 + 工具记录 + 审批提示
            parts = self._build_channel_reply(response)
            for text in parts:
                if text:
                    await adapter.send_message(conversation_id, text)

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

    # ==================== Channel 回复格式化 ====================

    def _build_channel_reply(self, response: ChatResponse) -> list[str]:
        """将 ChatResponse 格式化为 channel 可发送的文本段列表。

        返回 list[str] 是为了支持超长消息分段发送。
        """
        parts = []

        # 1. 正文
        if response.message:
            parts.append(response.message)

        # 2. 工具执行记录
        if response.tool_calls:
            tool_section = self._format_tool_calls(response.tool_calls)
            if tool_section:
                parts.append(tool_section)

        # 3. 审批请求
        if response.needs_approval and response.approval_info:
            approval_section = self._format_approval_request(response.approval_info)
            if approval_section:
                parts.append(approval_section)

        # 按长度分段
        return self._split_messages(parts)

    @staticmethod
    def _format_tool_calls(tool_calls) -> str:
        """格式化工具执行记录。"""
        lines = ["--- 工具执行记录 ---"]
        for tc in tool_calls:
            # 输入摘要
            input_str = json.dumps(tc.input, ensure_ascii=False)
            if len(input_str) > 200:
                input_str = input_str[:200] + "..."

            # 输出摘要
            output = tc.output or ""
            if len(output) > TOOL_OUTPUT_PREVIEW:
                output = output[:TOOL_OUTPUT_PREVIEW] + "..."

            lines.append(f"[{tc.name}]")
            if input_str != "{}":
                lines.append(f"  参数: {input_str}")
            lines.append(f"  结果: {output}")

        return "\n".join(lines)

    @staticmethod
    def _format_approval_request(approval_info) -> str:
        """格式化审批请求。"""
        lines = ["⚠️ 以下操作需要您的确认："]
        for info in approval_info:
            input_str = json.dumps(info.input, ensure_ascii=False)
            if len(input_str) > 300:
                input_str = input_str[:300] + "..."
            lines.append(f"▸ {info.name}: {input_str}")
        lines.append("")
        lines.append('请回复「确认」执行，或回复其他内容取消。')
        return "\n".join(lines)

    @staticmethod
    def _split_messages(parts: list[str]) -> list[str]:
        """将文本段按长度限制分割，避免单条消息过长。"""
        result = []
        current = ""

        for part in parts:
            if not current:
                current = part
            elif len(current) + len(part) + 2 <= MAX_MESSAGE_LENGTH:
                current = current + "\n\n" + part
            else:
                result.append(current)
                current = part

        if current:
            result.append(current)

        # 单条仍超长则截断
        return [m[:MAX_MESSAGE_LENGTH] for m in result]

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
