"""上下文管理器。

负责对话历史的压缩和管理，支持多次压缩场景。
基于 token 数量进行压缩判断。
支持工具结果清理（Tool-result Clearing）。
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Message
from backend.core.context.token_counter import TokenCounter, get_token_counter


class ContextManager:
    """上下文管理器。

    功能：
    1. 获取用于 LLM 的精简上下文（摘要 + 未压缩消息）
    2. 获取用于前端展示的完整消息
    3. 触发上下文压缩（可主动调用）
    4. 支持多次压缩（摘要也可以被压缩）
    5. 基于 token 数量进行压缩判断
    6. 工具结果清理（清理旧的、可重新获取的工具输出）

    压缩流程：
    ─────────────────────────────────────────────────────
    [msg1]...[msg10] → [SUMMARY_1] + [msg11]...[msg15]
                          │
                  is_summarized=True (msg1-msg10)

    [SUMMARY_1]...[msg25] → [SUMMARY_2] + [msg26]...[msg30]
           │                      │
           └── is_summarized=True └── is_summarized=True
    ─────────────────────────────────────────────────────

    工具结果清理：
    ─────────────────────────────────────────────────────
    保留最近 N 个工具结果，旧的用占位符替换：
    [tool_result content="500行输出..."] → [tool_result content="[cleared]"]
    ─────────────────────────────────────────────────────
    """

    # 默认 token 阈值（触发压缩）
    DEFAULT_TOKEN_THRESHOLD = 100000  # 100K tokens
    # 压缩后保留的 token 预算
    DEFAULT_KEEP_RECENT_TOKENS = 20000  # 20K tokens
    # 为响应保留的 token
    RESERVE_FOR_RESPONSE = 8000
    # 摘要角色标识
    SUMMARY_ROLE = "summary"
    # 工具结果清理占位符
    CLEARED_PLACEHOLDER = "[cleared to save context]"

    # 工具结果清理配置
    DEFAULT_CLEAR_TOOL_THRESHOLD = 80000  # 80K tokens 触发清理
    DEFAULT_KEEP_RECENT_TOOLS = 4  # 保留最近 4 个工具结果
    # 工具结果清理占位符
    CLEARED_PLACEHOLDER = "[cleared to save context]"

    # 可重新获取的工具名称（这些工具的结果可以安全清理）
    REFETCHABLE_TOOLS = {
        "read_file", "read_files", "list_files", "list_directory",
        "search_files", "grep", "glob", "search",
        "web_fetch", "web_search", "http_get", "http_request",
    }

    def __init__(
        self,
        token_threshold: int | None = None,
        keep_recent_tokens: int | None = None,
        model_id: str | None = None,
        clear_tool_threshold: int | None = None,
        keep_recent_tools: int | None = None,
    ):
        """初始化上下文管理器。

        Args:
            token_threshold: 触发压缩的 token 阈值
            keep_recent_tokens: 压缩后保留的 token 预算
            model_id: 模型 ID（用于确定上下文限制）
            clear_tool_threshold: 触发工具结果清理的 token 阈值
            keep_recent_tools: 保留的最近工具结果数量
        """
        self.token_threshold = token_threshold or self.DEFAULT_TOKEN_THRESHOLD
        self.keep_recent_tokens = keep_recent_tokens or self.DEFAULT_KEEP_RECENT_TOKENS
        self.clear_tool_threshold = clear_tool_threshold or self.DEFAULT_CLEAR_TOOL_THRESHOLD
        self.keep_recent_tools = keep_recent_tools or self.DEFAULT_KEEP_RECENT_TOOLS
        self.token_counter = get_token_counter(model_id)

    async def get_context_for_llm(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """获取用于 LLM 的上下文（精简版）。

        返回：摘要 + 未被压缩的近期消息

        Args:
            db: 数据库会话
            session_id: 会话 ID

        Returns:
            消息列表，格式为 [{"role": str, "content": str}, ...]
        """
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(
                # 包含摘要消息 或 未被压缩的消息
                (Message.role == self.SUMMARY_ROLE) | (Message.is_summarized == False)
            )
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        result_msgs = []
        for msg in messages:
            # HITL: 如果消息有 pending_approval，用结构化 content_blocks
            if (
                msg.meta_data
                and "pending_approval" in msg.meta_data
            ):
                blocks = msg.meta_data["pending_approval"]["content_blocks"]
                result_msgs.append({"role": msg.role, "content": blocks})
            # 中间工具交换：meta_data.content_blocks 存储结构化内容
            elif msg.meta_data and "content_blocks" in msg.meta_data:
                result_msgs.append({"role": msg.role, "content": msg.meta_data["content_blocks"]})
            else:
                result_msgs.append({"role": msg.role, "content": msg.content})
        return result_msgs

    async def get_messages_for_display(
        self,
        db: AsyncSession,
        session_id: str,
        include_summarized: bool = True,
    ) -> list[dict[str, Any]]:
        """获取用于前端展示的消息。

        Args:
            db: 数据库会话
            session_id: 会话 ID
            include_summarized: 是否包含已压缩的消息

        Returns:
            消息列表，包含完整信息
        """
        query = select(Message).where(Message.session_id == session_id)

        if not include_summarized:
            query = query.where(Message.is_summarized == False)

        query = query.order_by(Message.created_at)

        result = await db.execute(query)
        messages = result.scalars().all()

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "is_summarized": msg.is_summarized,
                "metadata": msg.meta_data,
            }
            for msg in messages
        ]

    async def should_compress(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> bool:
        """判断是否需要压缩上下文（基于 token 数量）。

        Args:
            db: 数据库会话
            session_id: 会话 ID

        Returns:
            是否需要压缩
        """
        # 获取未被压缩的消息
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .where(Message.role != self.SUMMARY_ROLE)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        if not messages:
            return False

        # 计算总 token 数
        message_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        total_tokens = self.token_counter.count_messages_tokens(message_dicts)

        return total_tokens > self.token_threshold

    async def compress_context(
        self,
        db: AsyncSession,
        session_id: str,
        llm_client: Any = None,
        keep_recent_tokens: int | None = None,
        keep_recent: int | None = None,
    ) -> dict[str, Any]:
        """压缩上下文（可主动调用）。

        将旧消息压缩成摘要，保留近期消息。
        支持两种保留策略：
        1. 基于 token 预算（keep_recent_tokens）
        2. 基于消息数量（keep_recent）

        Args:
            db: 数据库会话
            session_id: 会话 ID
            llm_client: LLM 客户端（用于生成摘要）
            keep_recent_tokens: 保留的近期消息 token 预算（优先）
            keep_recent: 保留的近期消息数量（备选）

        Returns:
            压缩结果信息
        """
        # 1. 获取所有未被压缩的消息（排除摘要）
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .where(Message.role != self.SUMMARY_ROLE)
            .order_by(Message.created_at)
        )
        all_messages = list(result.scalars().all())

        if not all_messages:
            return {
                "success": False,
                "reason": "No messages to compress",
                "message_count": 0,
            }

        # 2. 根据策略分割消息
        if keep_recent_tokens is not None:
            # 基于 token 预算
            to_compress, recent_messages, kept_tokens = self._split_by_token_budget(
                all_messages, keep_recent_tokens
            )
        elif keep_recent is not None:
            # 基于消息数量
            if len(all_messages) <= keep_recent:
                return {
                    "success": False,
                    "reason": "Not enough messages to compress",
                    "message_count": len(all_messages),
                }
            to_compress = all_messages[:-keep_recent]
            recent_messages = all_messages[-keep_recent:]
            kept_tokens = self.token_counter.count_messages_tokens(
                [{"role": m.role, "content": m.content} for m in recent_messages]
            )
        else:
            # 使用默认 token 预算
            to_compress, recent_messages, kept_tokens = self._split_by_token_budget(
                all_messages, self.keep_recent_tokens
            )

        if not to_compress:
            return {
                "success": False,
                "reason": "Not enough messages to compress",
                "message_count": len(all_messages),
            }

        # 3. 生成摘要
        summary_content = await self._generate_summary(to_compress, llm_client)

        # 4. 标记旧消息为已压缩
        compressed_ids = []
        compressed_tokens = 0
        for msg in to_compress:
            msg.is_summarized = True
            compressed_ids.append(msg.id)
            compressed_tokens += self.token_counter.count_message_tokens(
                {"role": msg.role, "content": msg.content}
            )

        # 5. 创建摘要消息
        summary_message = Message(
            session_id=session_id,
            role=self.SUMMARY_ROLE,
            content=summary_content,
            is_summarized=False,
            metadata={
                "compressed_message_ids": compressed_ids,
                "compressed_count": len(compressed_ids),
                "compressed_tokens": compressed_tokens,
                "compressed_at": datetime.utcnow().isoformat(),
            },
        )
        db.add(summary_message)

        # 6. 提交更改
        await db.flush()

        summary_tokens = self.token_counter.count_text_tokens(summary_content)

        return {
            "success": True,
            "compressed_count": len(compressed_ids),
            "compressed_tokens": compressed_tokens,
            "kept_count": len(recent_messages),
            "kept_tokens": kept_tokens,
            "summary_tokens": summary_tokens,
            "summary_id": summary_message.id,
        }

    def _split_by_token_budget(
        self,
        messages: list[Message],
        keep_budget: int,
    ) -> tuple[list[Message], list[Message], int]:
        """根据 token 预算分割消息。

        从最新消息开始逆向累积，保留在预算内的近期消息。

        Args:
            messages: 消息列表（按时间排序）
            keep_budget: 保留的 token 预算

        Returns:
            (要压缩的消息, 保留的消息, 保留消息的 token 数)
        """
        # 从最新消息开始，逆向累积
        recent = []
        recent_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.token_counter.count_message_tokens(
                {"role": msg.role, "content": msg.content}
            )

            if recent_tokens + msg_tokens <= keep_budget:
                recent.insert(0, msg)
                recent_tokens += msg_tokens
            else:
                # 预算用尽，停止添加
                break

        # 分割：要压缩的 + 保留的
        if recent:
            split_index = messages.index(recent[0])
            to_compress = messages[:split_index]
        else:
            to_compress = messages[:-1]  # 至少保留最后一条
            recent = [messages[-1]]
            recent_tokens = self.token_counter.count_message_tokens(
                {"role": messages[-1].role, "content": messages[-1].content}
            )

        return to_compress, recent, recent_tokens

    async def _generate_summary(
        self,
        messages: list[Message],
        llm_client: Any = None,
    ) -> str:
        """生成对话摘要。

        Args:
            messages: 要压缩的消息列表
            llm_client: LLM 客户端

        Returns:
            摘要内容
        """
        # 构建对话文本
        conversation_text = self._format_messages_for_summary(messages)

        # 如果有 LLM 客户端，使用 LLM 生成摘要
        if llm_client:
            return await self._generate_llm_summary(conversation_text, llm_client)

        # 否则使用简单的格式化摘要
        return self._generate_simple_summary(messages, conversation_text)

    def _format_messages_for_summary(self, messages: list[Message]) -> str:
        """格式化消息用于摘要生成。"""
        lines = []
        for msg in messages:
            role = msg.role.upper()
            content = msg.content[:500]  # 截断长消息
            if len(msg.content) > 500:
                content += "..."
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    async def _generate_llm_summary(
        self,
        conversation_text: str,
        llm_client: Any,
    ) -> str:
        """使用 LLM 生成摘要。"""
        try:
            # 使用传入的 LLM 客户端生成摘要
            response = llm_client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""请为以下对话生成一个简洁的摘要，保留关键信息、决策和重要上下文：

<conversation>
{conversation_text}
</conversation>

要求：
1. 保留关键的用户请求和需求
2. 保留重要的决策和结论
3. 保留关键的代码或技术细节
4. 使用简洁的中文描述
5. 摘要长度控制在 500 字以内"""
                    }
                ]
            )
            return f"<conversation_summary>\n{response.content[0].text}\n</conversation_summary>"
        except Exception as e:
            # 如果 LLM 调用失败，回退到简单摘要
            return self._generate_simple_summary(None, conversation_text)

    def _generate_simple_summary(
        self,
        messages: list[Message] | None,
        conversation_text: str,
    ) -> str:
        """生成简单摘要（不使用 LLM）。"""
        if messages:
            count = len(messages)
            first_msg = messages[0].created_at.strftime("%Y-%m-%d %H:%M")
            last_msg = messages[-1].created_at.strftime("%Y-%m-%d %H:%M")
            return f"""<conversation_summary>
[已压缩 {count} 条历史消息]
时间范围: {first_msg} ~ {last_msg}

对话内容概要:
{conversation_text[:1000]}
</conversation_summary>"""
        return f"""<conversation_summary>
[已压缩历史消息]

对话内容:
{conversation_text[:1000]}
</conversation_summary>"""

    async def get_context_stats(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict[str, Any]:
        """获取上下文统计信息（包含 token 统计）。

        Args:
            db: 数据库会话
            session_id: 会话 ID

        Returns:
            统计信息
        """
        # 获取所有消息
        all_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        all_messages = list(all_result.scalars().all())

        # 获取未压缩消息
        uncompressed_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .order_by(Message.created_at)
        )
        uncompressed_messages = list(uncompressed_result.scalars().all())

        # 获取摘要
        summary_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.role == self.SUMMARY_ROLE)
            .order_by(Message.created_at)
        )
        summary_messages = list(summary_result.scalars().all())

        # 计算 token 统计
        def messages_to_dicts(msgs):
            return [{"role": m.role, "content": m.content} for m in msgs]

        all_tokens = self.token_counter.count_messages_tokens(
            messages_to_dicts(all_messages)
        )
        uncompressed_tokens = self.token_counter.count_messages_tokens(
            messages_to_dicts(uncompressed_messages)
        )
        summary_tokens = self.token_counter.count_messages_tokens(
            messages_to_dicts(summary_messages)
        )

        # 计算上下文使用率
        context_limit = self.token_counter.context_limit
        usage_percentage = round(all_tokens / context_limit * 100, 2)

        return {
            "total_messages": len(all_messages),
            "total_tokens": all_tokens,
            "uncompressed_count": len(uncompressed_messages),
            "uncompressed_tokens": uncompressed_tokens,
            "compressed_count": len(all_messages) - len(uncompressed_messages),
            "summary_count": len(summary_messages),
            "summary_tokens": summary_tokens,
            "context_limit": context_limit,
            "usage_percentage": usage_percentage,
            "should_compress": uncompressed_tokens > self.token_threshold,
            "token_threshold": self.token_threshold,
        }

    # ==================== 工具结果清理 ====================

    async def should_clear_tools(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> bool:
        """判断是否需要清理工具结果（基于 token 数量）。

        Args:
            db: 数据库会话
            session_id: 会话 ID

        Returns:
            是否需要清理工具结果
        """
        # 获取未压缩消息的 token 数
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .where(Message.role != self.SUMMARY_ROLE)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        if not messages:
            return False

        message_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        total_tokens = self.token_counter.count_messages_tokens(message_dicts)

        return total_tokens > self.clear_tool_threshold

    async def clear_tool_results(
        self,
        db: AsyncSession,
        session_id: str,
        keep_recent: int | None = None,
        exclude_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """清理旧的工具结果，用占位符替换。

        将旧的 tool_result 内容替换为占位符，保留 tool_use 记录。
        适用于可重新获取的工具结果（如文件读取、API 查询）。

        Args:
            db: 数据库会话
            session_id: 会话 ID
            keep_recent: 保留的最近工具结果数量（默认 self.keep_recent_tools）
            exclude_tools: 排除的工具名称列表（这些工具的结果不会被清理）

        Returns:
            清理结果信息
        """
        keep = keep_recent or self.keep_recent_tools
        exclude_set = set(exclude_tools or [])

        # 1. 获取所有未压缩的 user 消息（可能包含 tool_result）
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .where(Message.role == "user")
            .order_by(Message.created_at)
        )
        user_messages = list(result.scalars().all())

        if not user_messages:
            return {
                "success": False,
                "reason": "No user messages to clear",
                "message_count": 0,
            }

        # 2. 解析消息内容，找出所有 tool_result
        all_tool_results = []  # [(msg, tool_use_id, tool_name, content)]
        for msg in user_messages:
            try:
                content = msg.content
                # content 可能是字符串或结构化内容
                if isinstance(content, str):
                    # 尝试解析为 JSON（tool_result 格式）
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            for block in parsed:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    tool_use_id = block.get("tool_use_id", "")
                                    tool_content = block.get("content", "")
                                    all_tool_results.append((msg, tool_use_id, None, tool_content))
                    except json.JSONDecodeError:
                        # 可能是纯文本，忽略
                        pass
                elif isinstance(content, list):
                    # 结构化内容
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_use_id = block.get("tool_use_id", "")
                            tool_content = block.get("content", "")
                            all_tool_results.append((msg, tool_use_id, None, tool_content))
            except Exception:
                continue

        if not all_tool_results:
            return {
                "success": False,
                "reason": "No tool results found",
                "tool_result_count": 0,
            }

        # 3. 找到对应的 tool_use 以获取工具名称
        # 获取 assistant 消息中的 tool_use
        assistant_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.is_summarized == False)
            .where(Message.role == "assistant")
            .order_by(Message.created_at)
        )
        assistant_messages = list(assistant_result.scalars().all())

        # 构建 tool_use_id -> tool_name 映射
        tool_name_map = {}
        for msg in assistant_messages:
            try:
                content = msg.content
                blocks = []
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            blocks = parsed
                    except json.JSONDecodeError:
                        pass
                elif isinstance(content, list):
                    blocks = content

                for block in blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_id = block.get("id", "")
                        tool_name = block.get("name", "")
                        tool_name_map[tool_id] = tool_name
            except Exception:
                continue

        # 4. 标记可清理的工具结果
        # 保留最近的 N 个，排除不可重新获取的工具
        cleared_count = 0
        cleared_tokens = 0
        kept_count = 0

        # 按消息时间排序，从旧到新
        tool_results_with_index = list(enumerate(all_tool_results))

        # 确定要清理的范围（保留最近的 keep 个）
        total_count = len(tool_results_with_index)
        clear_from = max(0, total_count - keep)

        for idx, (msg, tool_use_id, _, tool_content) in tool_results_with_index:
            tool_name = tool_name_map.get(tool_use_id, "")

            # 检查是否在保留窗口内
            if idx >= clear_from:
                kept_count += 1
                continue

            # 检查是否在排除列表中
            if tool_name in exclude_set:
                kept_count += 1
                continue

            # 检查是否是可重新获取的工具
            # 如果工具不在可重新获取列表中，则保留
            if tool_name and tool_name not in self.REFETCHABLE_TOOLS:
                kept_count += 1
                continue

            # 5. 执行清理：替换消息内容中的 tool_result
            original_tokens = self.token_counter.count_text_tokens(tool_content)

            try:
                content = msg.content
                new_content = None

                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            for block in parsed:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    if block.get("tool_use_id") == tool_use_id:
                                        block["content"] = self.CLEARED_PLACEHOLDER
                            new_content = json.dumps(parsed, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            if block.get("tool_use_id") == tool_use_id:
                                block["content"] = self.CLEARED_PLACEHOLDER
                    new_content = content  # 保持 list 格式

                if new_content:
                    msg.content = new_content
                    cleared_count += 1
                    cleared_tokens += original_tokens
            except Exception:
                continue

        if cleared_count > 0:
            await db.flush()

        return {
            "success": True,
            "cleared_count": cleared_count,
            "cleared_tokens": cleared_tokens,
            "kept_count": kept_count,
            "total_tool_results": total_count,
        }

    async def clear_and_compress(
        self,
        db: AsyncSession,
        session_id: str,
        llm_client: Any = None,
        keep_recent_tools: int | None = None,
        keep_recent_tokens: int | None = None,
    ) -> dict[str, Any]:
        """先清理工具结果，再压缩上下文。

        组合策略：先清理可重新获取的工具结果，释放空间。
        如果仍然超过阈值，再进行摘要压缩。

        Args:
            db: 数据库会话
            session_id: 会话 ID
            llm_client: LLM 客户端（用于生成摘要）
            keep_recent_tools: 保留的最近工具结果数量
            keep_recent_tokens: 压缩后保留的 token 预算

        Returns:
            包含清理和压缩结果的字典
        """
        results = {
            "clear_result": None,
            "compress_result": None,
        }

        # 1. 先尝试清理工具结果
        if await self.should_clear_tools(db, session_id):
            clear_result = await self.clear_tool_results(
                db, session_id, keep_recent=keep_recent_tools
            )
            results["clear_result"] = clear_result

        # 2. 检查是否仍需压缩
        if await self.should_compress(db, session_id):
            compress_result = await self.compress_context(
                db, session_id, llm_client, keep_recent_tokens=keep_recent_tokens
            )
            results["compress_result"] = compress_result

        return results


# 全局上下文管理器实例
context_manager = ContextManager()
