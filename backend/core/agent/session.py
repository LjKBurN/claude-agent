"""SessionManager — 会话管理门面。

封装 DB 会话 CRUD、消息保存、HITL 恢复等操作。
从 agent_service.py 提取而来，委托给 ContextManager 进行上下文压缩。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.agent.utils import extract_text, serialize_blocks
from backend.core.context.manager import context_manager
from backend.db.models import Message, Session

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器。

    职责：
    1. 会话的创建和查找
    2. 消息的保存和读取
    3. HITL 审批状态管理
    4. 上下文压缩的触发（带缓存，避免每次请求都查 DB）
    """

    # 压缩检查间隔（秒）
    COMPRESS_CHECK_INTERVAL = 60
    # 累积 N 条新消息后强制检查
    COMPRESS_CHECK_MSG_THRESHOLD = 5
    # 缓存 session 上限（LRU 淘汰）
    MAX_CACHED_SESSIONS = 1000

    def __init__(self, llm_provider=None):
        """
        Args:
            llm_provider: LLMProvider 实例，用于上下文压缩的摘要生成
        """
        self._llm = llm_provider
        self._compress_check_times: OrderedDict[str, float] = OrderedDict()
        self._compress_msg_counts: dict[str, int] = {}

    def invalidate_compress_cache(self, session_id: str) -> None:
        """手动压缩后调用，清除缓存以使下次 get_messages 强制检查。"""
        self._compress_check_times.pop(session_id, None)
        self._compress_msg_counts.pop(session_id, None)

    def set_llm(self, llm_provider) -> None:
        """设置 LLM Provider（延迟注入）。"""
        self._llm = llm_provider

    # ==================== 会话管理 ====================

    async def get_or_create_session(
        self, db: AsyncSession, session_id: str | None
    ) -> Session:
        """获取或创建会话。"""
        if session_id:
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                return session

        session = Session(id=str(uuid.uuid4()))
        db.add(session)
        await db.flush()
        return session

    # ==================== 消息管理 ====================

    async def save_message(
        self, db: AsyncSession, session_id: str, role: str, content: str
    ) -> Message:
        """保存消息。"""
        message = Message(session_id=session_id, role=role, content=content)
        db.add(message)
        await db.flush()
        return message

    async def get_messages(
        self, db: AsyncSession, session_id: str
    ) -> list[dict]:
        """获取会话历史消息（用于 LLM 上下文）。

        基于缓存间隔检查是否需要压缩，避免每次请求都查询 DB。
        自动检查并触发：
        1. 工具结果清理（如果工具结果占用过多 token）
        2. 上下文压缩（如果总 token 超过阈值）
        """
        if self._should_check_compression(session_id):
            needs_compress = await context_manager.should_compress(db, session_id)
            self._record_compress_check(session_id)
            if needs_compress:
                await self._auto_clear_and_compress(db, session_id)
        else:
            self._compress_msg_counts[session_id] = (
                self._compress_msg_counts.get(session_id, 0) + 1
            )

        return await context_manager.get_context_for_llm(db, session_id)

    def _should_check_compression(self, session_id: str) -> bool:
        """判断是否需要检查压缩（基于间隔和消息计数）。"""
        msg_count = self._compress_msg_counts.get(session_id, 0)
        if msg_count >= self.COMPRESS_CHECK_MSG_THRESHOLD:
            return True

        last_check = self._compress_check_times.get(session_id, 0)
        return (time.monotonic() - last_check) >= self.COMPRESS_CHECK_INTERVAL

    def _record_compress_check(self, session_id: str) -> None:
        """记录压缩检查时间，LRU 淘汰超限 session。"""
        self._compress_check_times[session_id] = time.monotonic()
        self._compress_check_times.move_to_end(session_id)
        self._compress_msg_counts[session_id] = 0

        # LRU 淘汰
        while len(self._compress_check_times) > self.MAX_CACHED_SESSIONS:
            oldest, _ = self._compress_check_times.popitem(last=False)
            self._compress_msg_counts.pop(oldest, None)

    async def _auto_clear_and_compress(self, db: AsyncSession, session_id: str) -> None:
        """自动清理工具结果和压缩上下文。"""
        if not self._llm:
            logger.warning("No LLM provider set, skipping compression")
            return

        result = await context_manager.clear_and_compress(
            db=db,
            session_id=session_id,
            llm_provider=self._llm,
        )

        clear_ok = result.get("clear_result", {}).get("success")
        compress_ok = result.get("compress_result", {}).get("success")
        if clear_ok or compress_ok:
            await db.flush()

    # ==================== 中间消息保存 ====================

    async def save_intermediate_messages(
        self, db: AsyncSession, session_id: str,
        messages: list[dict], original_count: int,
    ) -> None:
        """将 agent loop 中的中间工具交换保存到 DB。"""
        for msg in messages[original_count:]:
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, str):
                await self.save_message(db, session_id, role, content)
            elif isinstance(content, list):
                if role == "assistant":
                    text = extract_text(content)
                    blocks = serialize_blocks(content)
                else:
                    text = ""
                    blocks = content
                m = Message(
                    session_id=session_id, role=role, content=text,
                    meta_data={"content_blocks": blocks},
                )
                db.add(m)
        await db.flush()

    # ==================== HITL 审批状态管理 ====================

    async def check_pending_approval(
        self, db: AsyncSession, session_id: str
    ) -> list[dict] | None:
        """检查是否有等待审批的 tool_use。返回 content_blocks 或 None。"""
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = result.scalar_one_or_none()

        if not last_msg:
            logger.info(f"HITL check: no assistant msg for session {session_id[:8]}")
            return None

        has_meta = last_msg.meta_data is not None
        has_pending = has_meta and "pending_approval" in last_msg.meta_data
        logger.info(
            f"HITL check: session={session_id[:8]}, msg_id={last_msg.id}, "
            f"has_meta={has_meta}, has_pending={has_pending}, "
            f"meta_keys={list(last_msg.meta_data.keys()) if has_meta else []}"
        )

        if has_pending:
            return last_msg.meta_data["pending_approval"]["content_blocks"]
        return None

    async def save_approval_message(
        self, db: AsyncSession, session_id: str,
        text: str, content_blocks: list[dict],
    ) -> None:
        """保存带 pending_approval 标记的 assistant 消息。"""
        meta = {
            "pending_approval": {
                "content_blocks": content_blocks,
            }
        }
        msg = Message(
            session_id=session_id,
            role="assistant",
            content=text,
            meta_data=meta,
        )
        db.add(msg)
        await db.flush()

    async def clear_pending_approval(
        self, db: AsyncSession, session_id: str,
    ) -> None:
        """清除 pending approval 标记。"""
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        pending_msg = result.scalar_one_or_none()
        if pending_msg and pending_msg.meta_data:
            pending_msg.meta_data = None

    async def build_resume_messages(
        self, db: AsyncSession, session: Session,
        user_message: str, pending_blocks: list[dict],
        tool_executor_fn=None,
    ) -> list[dict]:
        """构建 HITL 恢复所需的消息列表。

        Args:
            tool_executor_fn: 工具执行函数 async (name, input, id, messages) -> str

        Returns:
            可直接传给 AgentLoop 的消息列表
        """
        await self.save_message(db, session.id, "user", user_message)
        await self.clear_pending_approval(db, session.id)

        all_messages = await self.get_messages(db, session.id)
        logger.info(
            f"HITL resume: loaded {len(all_messages)} messages from DB, "
            f"user_message={user_message!r}"
        )
        messages = all_messages[:-2]
        messages.append({"role": "assistant", "content": pending_blocks})

        is_approved = "确认" in user_message or "confirm" in user_message.lower()
        tool_results = []
        for block in pending_blocks:
            if block.get("type") != "tool_use":
                continue
            if is_approved and tool_executor_fn:
                output = await tool_executor_fn(
                    block["name"], block["input"], block["id"], messages
                )
                logger.info(
                    f"HITL execute: tool={block['name']}, "
                    f"output_len={len(output)}, output_preview={output[:200]!r}"
                )
            else:
                output = f"用户取消了此操作。用户说：{user_message}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": output,
            })

        messages.append({"role": "user", "content": tool_results})
        return messages

    # ==================== 上下文管理（公开接口） ====================

    async def compress_session(
        self, db: AsyncSession, session_id: str,
        keep_recent: int | None = None,
    ) -> dict[str, Any]:
        """主动压缩会话上下文。"""
        if not self._llm:
            return {"success": False, "error": "No LLM provider"}

        result = await context_manager.compress_context(
            db=db,
            session_id=session_id,
            llm_provider=self._llm,
            keep_recent=keep_recent,
        )
        if result.get("success"):
            await db.flush()
        return result

    async def get_session_stats(
        self, db: AsyncSession, session_id: str,
    ) -> dict[str, Any]:
        """获取会话上下文统计信息。"""
        return await context_manager.get_context_stats(db, session_id)

    async def get_display_messages(
        self, db: AsyncSession, session_id: str,
        include_summarized: bool = True,
    ) -> list[dict]:
        """获取用于前端展示的消息。"""
        return await context_manager.get_messages_for_display(
            db, session_id, include_summarized
        )

