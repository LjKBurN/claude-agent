"""Agent 服务封装。"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.chat import ChatResponse, ToolCall
from backend.config import get_settings
from backend.db.models import Message, Session
from backend.core.skills.registry import skill_registry
from backend.core.tools import get_tools
from backend.core.tool_executor import tool_executor
from backend.core.mcp.manager import mcp_manager
from backend.core.context.manager import context_manager

logger = logging.getLogger(__name__)

# Agent 执行保护常量
MAX_TOOL_ITERATIONS = 20       # 工具循环最大次数
API_MAX_RETRIES = 3            # API 可恢复错误最大重试次数
TOOL_EXECUTION_TIMEOUT = 120   # 单个工具执行超时（秒）


class AgentService:
    """Agent 服务类。"""

    def __init__(self):
        self.settings = get_settings()
        self._mcp_initialized = False
        self._anthropic_client = None  # 用于摘要生成

    async def _ensure_mcp_initialized(self) -> None:
        """确保 MCP 已初始化。"""
        if self._mcp_initialized:
            return

        # 加载 MCP 配置（Claude Code 格式）
        # 1. 用户级：~/.claude.json
        # 2. 项目级：.mcp.json
        from pathlib import Path
        project_root = Path(self.settings.mcp_config_path).parent
        mcp_manager.load_all_configs(project_root)
        await mcp_manager.initialize()

        self._mcp_initialized = True

    def _get_all_tools(self) -> list[dict]:
        """获取所有工具，包含 Skill meta-tool 和 MCP tools。"""
        # 1. 内置工具
        tools = get_tools()

        # 2. Skill meta-tool
        tools.append(skill_registry.get_skill_tool_definition())

        # 3. MCP Tools（支持延迟加载）
        mcp_tools, lazy_mode = mcp_manager.get_tools_for_api()
        tools.extend(mcp_tools)

        return tools

    def _get_client_kwargs(self) -> dict:
        """获取 Anthropic 客户端配置。"""
        kwargs = {"api_key": self.settings.anthropic_api_key}
        if self.settings.anthropic_base_url:
            kwargs["base_url"] = self.settings.anthropic_base_url
        return kwargs

    # ==================== 错误恢复 ====================

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """判断 API 错误是否可重试。"""
        from anthropic import (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            OverloadedError,
            RateLimitError,
            ServiceUnavailableError,
        )

        return isinstance(exc, (
            RateLimitError,
            InternalServerError,
            OverloadedError,
            ServiceUnavailableError,
            APITimeoutError,
            APIConnectionError,
        ))

    async def _call_with_retry(self, client, messages, tools, system):
        """带重试的 API 调用（非流式）。"""
        for attempt in range(API_MAX_RETRIES):
            try:
                return client.messages.create(
                    model=self.settings.model_id,
                    max_tokens=8000,
                    tools=tools,
                    messages=messages,
                    system=system,
                )
            except Exception as e:
                if not self._is_retryable_error(e) or attempt == API_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"API error (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{type(e).__name__}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)

    async def _stream_with_retry(self, client, messages, tools, system):
        """带重试的 API 流式调用。"""
        for attempt in range(API_MAX_RETRIES):
            try:
                return client.messages.stream(
                    model=self.settings.model_id,
                    max_tokens=4096,
                    tools=tools,
                    messages=messages,
                    system=system,
                )
            except Exception as e:
                if not self._is_retryable_error(e) or attempt == API_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"API stream error (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{type(e).__name__}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)

    def _check_tool_permission(
        self, tool_name: str, tool_input: dict, mcp_tool_names: set[str]
    ) -> bool:
        """检查工具是否安全可自动执行。

        Returns:
            True = 安全，False = 需要审批
        """
        from backend.core.tools.base import get_tool

        # 已注册工具：使用 tool.is_safe() 判断（支持细粒度）
        tool = get_tool(tool_name)
        if tool:
            return tool.is_safe(tool_input)

        # MCP 动态工具：默认需要审批
        if tool_name in mcp_tool_names:
            return False

        # 未知工具：需要审批
        return False

    def _get_dangerous_tools(self, content_blocks) -> list[dict]:
        """从 LLM 响应中提取需要审批的 tool_use blocks。"""
        mcp_tool_names = self._get_mcp_tool_names()
        dangerous = []
        for block in content_blocks:
            if block.type != "tool_use":
                continue
            if not self._check_tool_permission(block.name, block.input, mcp_tool_names):
                dangerous.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return dangerous

    @staticmethod
    def _serialize_content_blocks(content_blocks) -> list[dict]:
        """将 Anthropic content blocks 序列化为可 JSON 化的 dict 列表。"""
        result = []
        for block in content_blocks:
            if hasattr(block, "text"):
                result.append({"type": "text", "text": block.text})
            elif hasattr(block, "type") and block.type == "tool_use":
                result.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif hasattr(block, "type") and block.type == "tool_result":
                entry = {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                }
                result.append(entry)
        return result

    async def _save_intermediate_messages(
        self, db, session_id, messages, original_count
    ):
        """将 agent loop 中的中间工具交换保存到 DB。

        assistant 消息: content=文本, meta_data.content_blocks=结构化内容
        user 消息(tool_result): content="", meta_data.content_blocks=tool_result 列表
        """
        for msg in messages[original_count:]:
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, str):
                await self._save_message(db, session_id, role, content)
            elif isinstance(content, list):
                if role == "assistant":
                    text = self._extract_text(content)
                    blocks = self._serialize_content_blocks(content)
                else:
                    text = ""
                    blocks = content  # tool_results 已经是 dict 列表
                m = Message(
                    session_id=session_id, role=role, content=text,
                    meta_data={"content_blocks": blocks},
                )
                db.add(m)
        await db.flush()

    async def _check_pending_approval(self, db, session_id):
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

    @staticmethod
    async def _save_approval_message(
        db, session_id, text, content_blocks
    ):
        """保存带 pending_approval 标记的 assistant 消息。

        content_blocks 已经是序列化后的 list[dict]，直接存储。
        """
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

    async def _clear_pending_approval(self, db, session_id):
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

    async def _build_resume_messages(
        self, db, session, user_message, pending_blocks
    ) -> list[dict]:
        """构建 HITL 恢复所需的消息列表。

        执行/拒绝 pending 工具，返回可直接传给 _run_agent / _run_agent_stream 的消息列表。
        """
        await self._save_message(db, session.id, "user", user_message)
        await self._clear_pending_approval(db, session.id)

        # 加载历史（DB 已包含中间工具交换），移除 pending assistant + user "确认"
        all_messages = await self._get_messages(db, session.id)
        logger.info(
            f"HITL resume: loaded {len(all_messages)} messages from DB, "
            f"user_message={user_message!r}"
        )
        messages = all_messages[:-2]
        messages.append({"role": "assistant", "content": pending_blocks})

        # 执行或拒绝 pending 工具
        is_approved = "确认" in user_message or "confirm" in user_message.lower()
        tool_results = []
        for block in pending_blocks:
            if block.get("type") != "tool_use":
                continue
            if is_approved:
                output, _ = await self._execute_tool(
                    tool_name=block["name"],
                    tool_input=block["input"],
                    tool_id=block["id"],
                    messages=messages,
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

    async def _handle_agent_result(
        self, db, session, response_text, tool_calls, approval_info,
        content_blocks, original_count=None, agent_messages=None,
    ) -> ChatResponse:
        """处理 agent 执行结果（保存消息，返回响应）。"""
        if approval_info:
            # 保存中间工具交换到 DB（在 pending 消息之前）
            if agent_messages and original_count is not None:
                await self._save_intermediate_messages(
                    db, session.id, agent_messages, original_count
                )
            await self._save_approval_message(
                db, session.id, response_text, content_blocks,
            )
            await db.commit()
            return ChatResponse(
                session_id=session.id,
                message=response_text,
                tool_calls=tool_calls,
                needs_approval=True,
                approval_info=approval_info,
            )

        await self._save_message(db, session.id, "assistant", response_text)
        await db.commit()
        return ChatResponse(
            session_id=session.id,
            message=response_text,
            tool_calls=tool_calls,
        )

    # ==================== 公开接口 ====================

    async def chat(
        self,
        user_message: str,
        session_id: str | None,
        db: AsyncSession,
    ) -> ChatResponse:
        """处理聊天请求（非流式）。"""
        await self._ensure_mcp_initialized()

        session = await self._get_or_create_session(db, session_id)

        # HITL 恢复 或 正常流程
        pending_blocks = await self._check_pending_approval(db, session.id)
        if pending_blocks:
            messages = await self._build_resume_messages(
                db, session, user_message, pending_blocks
            )
        else:
            await self._save_message(db, session.id, "user", user_message)
            messages = await self._get_messages(db, session.id)

        response_text, tool_calls, approval_info, content_blocks, original_count, agent_messages = (
            await self._run_agent(messages)
        )
        return await self._handle_agent_result(
            db, session, response_text, tool_calls, approval_info,
            content_blocks, original_count, agent_messages,
        )

    async def chat_stream(
        self,
        user_message: str,
        session_id: str | None,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """处理聊天请求（流式）。"""
        await self._ensure_mcp_initialized()

        session = await self._get_or_create_session(db, session_id)
        logger.info(
            f"chat_stream: user_message={user_message!r}, "
            f"session_id={session.id[:8]}, request_sid={session_id[:8] if session_id else None}"
        )

        # HITL 恢复 或 正常流程
        pending_blocks = await self._check_pending_approval(db, session.id)
        if pending_blocks:
            messages = await self._build_resume_messages(
                db, session, user_message, pending_blocks
            )
        else:
            await self._save_message(db, session.id, "user", user_message)
            messages = await self._get_messages(db, session.id)

        async for event in self._stream_agent_response(db, session, messages):
            yield event

    async def _stream_agent_response(
        self, db, session, messages
    ) -> AsyncGenerator[str, None]:
        """运行 agent 流式响应并 yield SSE 事件（流式共用逻辑）。"""
        yield self._sse_event("session_id", {"session_id": session.id})

        full_response = ""
        tool_calls: list[ToolCall] = []

        async for event in self._run_agent_stream(messages):
            if event["type"] == "text":
                full_response += event["content"]
                yield self._sse_event("text", {"content": event["content"]})
            elif event["type"] == "tool_start":
                yield self._sse_event("tool_start", {"name": event["name"]})
            elif event["type"] == "tool_end":
                tool_calls.append(event["tool_call"])
                yield self._sse_event("tool_end", {
                    "name": event["tool_call"].name,
                    "output": event["tool_call"].output,
                })
            elif event["type"] == "skill_load":
                yield self._sse_event("skill_load", {
                    "name": event["skill_name"],
                    "message": event["message"],
                })
            elif event["type"] == "mcp_tools_loaded":
                yield self._sse_event("mcp_tools_loaded", {
                    "count": event["count"],
                    "tools": event["tools"],
                })
            elif event["type"] == "approval_needed":
                # 保存中间工具交换到 DB（在 pending 消息之前）
                await self._save_intermediate_messages(
                    db, session.id, event["messages"], event["original_count"]
                )
                await self._save_approval_message(
                    db, session.id, full_response, event["content_blocks"]
                )
                await db.commit()
                yield self._sse_event("approval_needed", {
                    "message": full_response,
                    "tools": event["tools"],
                })
                yield self._sse_event("done", {"status": "needs_approval"})
                return

        await self._save_message(db, session.id, "assistant", full_response)
        await db.commit()

        yield self._sse_event("done", {"tool_calls": [
            {"name": tc.name, "input": tc.input, "output": tc.output}
            for tc in tool_calls
        ]})

    # ==================== 会话管理 ====================

    async def _get_or_create_session(
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

    async def _save_message(
        self, db: AsyncSession, session_id: str, role: str, content: str
    ) -> Message:
        """保存消息。"""
        message = Message(session_id=session_id, role=role, content=content)
        db.add(message)
        await db.flush()
        return message

    async def _get_messages(self, db: AsyncSession, session_id: str) -> list[dict]:
        """获取会话历史消息（用于 LLM 上下文）。

        自动检查并触发：
        1. 工具结果清理（如果工具结果占用过多 token）
        2. 上下文压缩（如果总 token 超过阈值）
        """
        # 使用组合策略：先清理工具结果，再压缩
        if await context_manager.should_compress(db, session_id):
            await self._auto_clear_and_compress(db, session_id)

        # 使用 ContextManager 获取精简上下文
        return await context_manager.get_context_for_llm(db, session_id)

    async def _auto_clear_and_compress(self, db: AsyncSession, session_id: str) -> None:
        """自动清理工具结果和压缩上下文。"""
        from anthropic import Anthropic

        # 获取客户端用于摘要生成
        if not self._anthropic_client:
            self._anthropic_client = Anthropic(**self._get_client_kwargs())

        result = await context_manager.clear_and_compress(
            db=db,
            session_id=session_id,
            llm_client=self._anthropic_client,
        )

        if result.get("clear_result", {}).get("success") or result.get("compress_result", {}).get("success"):
            # 有成功操作，提交更改
            await db.flush()

    # ==================== 上下文管理（公开接口） ====================

    async def compress_session(
        self,
        db: AsyncSession,
        session_id: str,
        keep_recent: int | None = None,
    ) -> dict[str, Any]:
        """主动压缩会话上下文。

        Args:
            db: 数据库会话
            session_id: 会话 ID
            keep_recent: 保留的近期消息数量（可选）

        Returns:
            压缩结果信息
        """
        from anthropic import Anthropic

        if not self._anthropic_client:
            self._anthropic_client = Anthropic(**self._get_client_kwargs())

        result = await context_manager.compress_context(
            db=db,
            session_id=session_id,
            llm_client=self._anthropic_client,
            keep_recent=keep_recent,
        )

        if result.get("success"):
            await db.flush()

        return result

    async def get_session_stats(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict[str, Any]:
        """获取会话上下文统计信息。"""
        return await context_manager.get_context_stats(db, session_id)

    async def get_display_messages(
        self,
        db: AsyncSession,
        session_id: str,
        include_summarized: bool = True,
    ) -> list[dict]:
        """获取用于前端展示的消息。"""
        return await context_manager.get_messages_for_display(
            db, session_id, include_summarized
        )

    # ==================== Agent 执行 ====================

    async def _run_agent(
        self, messages: list[dict]
    ) -> tuple[str, list[ToolCall], list[dict] | None, list[dict] | None,
                int, list[dict]]:
        """运行 Agent（非流式）。

        Returns:
            (text, tool_calls, approval_info, content_blocks, original_count, messages)
        """
        from anthropic import Anthropic

        client = Anthropic(**self._get_client_kwargs())
        tools = self._get_all_tools()
        tool_calls: list[ToolCall] = []
        system = "You are a helpful assistant."
        original_count = len(messages)

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = await self._call_with_retry(client, messages, tools, system)
            except Exception as e:
                logger.error(f"API call failed after retries: {e}")
                return f"[Error] API 调用失败: {type(e).__name__}", tool_calls, None, None, original_count, messages

            if response.stop_reason == "tool_use":
                # HITL: 检查是否有 dangerous 工具
                dangerous = self._get_dangerous_tools(response.content)
                if dangerous:
                    text = self._extract_text(response.content)
                    serialized = self._serialize_content_blocks(response.content)
                    tool_names = [t["name"] for t in dangerous]
                    logger.info(
                        f"HITL: {len(dangerous)} tool(s) need approval: {tool_names}"
                    )
                    return text, tool_calls, dangerous, serialized, original_count, messages

                messages.append({"role": "assistant", "content": response.content})
                tool_results, new_tools = await self._process_tool_calls(
                    response.content, tool_calls, messages, tools
                )
                if new_tools:
                    tools.extend(new_tools)
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                text = self._extract_text(response.content)
                return text, tool_calls, None, None, original_count, messages

            else:
                text = self._extract_text(response.content)
                return text or f"Stopped: {response.stop_reason}", tool_calls, None, None, original_count, messages

        logger.warning(f"Agent reached max iterations ({MAX_TOOL_ITERATIONS})")
        return "[Error] Agent 达到最大工具调用次数，请简化请求", tool_calls, None, None, original_count, messages

    async def _run_agent_stream(
        self, messages: list[dict]
    ) -> AsyncGenerator[dict, None]:
        """运行 Agent（流式）。

        流式期间只收集 tool_use 信息（不执行），流结束后：
        1. HITL 检查 — 有 dangerous 工具则退出等待审批
        2. 全部安全 — 执行工具，yield tool_end 事件，继续循环
        """
        from anthropic import Anthropic

        client = Anthropic(**self._get_client_kwargs())
        all_tools = self._get_all_tools()
        system = "You are a helpful assistant."
        original_count = len(messages)

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                stream_ctx = await self._stream_with_retry(client, messages, all_tools, system)
            except Exception as e:
                logger.error(f"API stream failed after retries: {e}")
                yield {"type": "text", "content": f"[Error] API 调用失败: {type(e).__name__}"}
                return

            with stream_ctx as stream:
                current_tool: dict[str, Any] | None = None

                for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield {"type": "text", "content": event.delta.text}

                    elif event.type == "content_block_start":
                        if hasattr(event.content_block, "type"):
                            if event.content_block.type == "tool_use":
                                current_tool = {
                                    "id": event.content_block.id,
                                    "name": event.content_block.name,
                                    "input": "",
                                }
                                yield {
                                    "type": "tool_start",
                                    "name": event.content_block.name,
                                }

                    elif event.type == "content_block_stop":
                        # 不在流式期间执行工具，只缓冲
                        current_tool = None

                final_message = stream.get_final_message()

                if final_message.stop_reason == "tool_use":
                    # HITL: 先检查是否有 dangerous 工具
                    dangerous = self._get_dangerous_tools(final_message.content)
                    tool_names_in_response = [
                        b.name for b in final_message.content
                        if hasattr(b, "type") and b.type == "tool_use"
                    ]
                    logger.info(
                        f"Agent stop_reason=tool_use, all_tools={tool_names_in_response}, "
                        f"dangerous={[t['name'] for t in dangerous] if dangerous else []}, "
                        f"msg_count={len(messages)}, original_count={original_count}"
                    )
                    if dangerous:
                        tool_names = [t["name"] for t in dangerous]
                        logger.info(
                            f"HITL stream: {len(dangerous)} tool(s) need approval: {tool_names}"
                        )
                        yield {
                            "type": "approval_needed",
                            "content_blocks": self._serialize_content_blocks(
                                final_message.content
                            ),
                            "tools": dangerous,
                            "messages": messages,
                            "original_count": original_count,
                        }
                        return

                    # 全部安全：执行工具并 yield 结果
                    messages.append({
                        "role": "assistant",
                        "content": final_message.content,
                    })
                    tool_results = []
                    for block in final_message.content:
                        if block.type != "tool_use":
                            continue

                        output, extra_events = await self._execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            tool_id=block.id,
                            messages=messages,
                            tools=all_tools,
                        )

                        # 处理 MCP Search 等动态工具注册
                        if extra_events:
                            for evt in extra_events:
                                yield evt
                                if evt.get("type") == "mcp_tools_loaded" and evt.get("tools"):
                                    pass  # tools already extended in _execute_tool

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        })

                        # yield tool_end 事件给前端
                        yield {
                            "type": "tool_end",
                            "tool_call": ToolCall(
                                name=block.name,
                                input=block.input,
                                output=output,
                            ),
                        }

                    messages.append({"role": "user", "content": tool_results})
                else:
                    return

        logger.warning(f"Agent stream reached max iterations ({MAX_TOOL_ITERATIONS})")
        yield {"type": "text", "content": "[Error] Agent 达到最大工具调用次数，请简化请求"}

    # ==================== 工具处理 ====================

    def _get_mcp_tool_names(self) -> set[str]:
        """获取所有 MCP 工具名称集合（带缓存）。"""
        return {t.name for t in mcp_manager.get_all_tools()}

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tool_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[str, list[dict] | None]:
        """统一的工具执行入口。

        工具执行失败时返回错误文本给 LLM，而不是抛出异常。
        LLM 可以根据错误信息决定重试或换策略。

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_id: 工具调用 ID
            messages: 消息列表（用于 Skill 注入）
            tools: 工具列表（用于动态注册 MCP 工具）

        Returns:
            (output, events) - 工具输出和可选的事件列表
        """
        mcp_tool_names = self._get_mcp_tool_names()

        # 权限检查（兜底：正常情况 HITL 已在 agent loop 层拦截）
        is_safe = self._check_tool_permission(tool_name, tool_input, mcp_tool_names)
        if not is_safe:
            logger.warning(
                f"Tool '{tool_name}' bypassed HITL check (should not happen)"
            )

        try:
            # 检查是否是 MCP 工具（加超时）
            if tool_name in mcp_tool_names:
                output = await asyncio.wait_for(
                    mcp_manager.call_tool(tool_name, tool_input),
                    timeout=TOOL_EXECUTION_TIMEOUT,
                )
                return output, None

            # 使用 ToolExecutor 执行（内置工具 + Skill + MCP Search）
            result = tool_executor.execute(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_id=tool_id,
            )

            events = []

            # 如果是 Skill，注入消息
            if result.messages_to_inject:
                messages.extend(result.messages_to_inject)
                skill_name = tool_input.get("command", "")
                events.append({
                    "type": "skill_load",
                    "skill_name": skill_name,
                    "message": f'The "{skill_name}" skill is loading'
                })

            # 如果是 MCP Search，注册新发现的工具
            if result.tools_to_register and tools is not None:
                tools.extend(result.tools_to_register)
                events.append({
                    "type": "mcp_tools_loaded",
                    "count": len(result.tools_to_register),
                    "tools": [t["name"] for t in result.tools_to_register],
                })

            return result.output, events if events else None

        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' timed out ({TOOL_EXECUTION_TIMEOUT}s)"
            logger.warning(error_msg)
            return error_msg, None
        except Exception as e:
            error_msg = f"Tool '{tool_name}' failed: {type(e).__name__}: {str(e)[:500]}"
            logger.error(error_msg)
            return error_msg, None

    async def _process_tool_calls(
        self,
        content_blocks,
        tool_calls: list[ToolCall],
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """处理工具调用（非流式）。

        单个工具失败不中断循环，错误信息返回给 LLM。

        Returns:
            (tool_results, new_tools) - 工具结果列表和需要注册的新工具
        """
        results = []
        new_tools = []

        for block in content_blocks:
            if block.type != "tool_use":
                continue

            output, _ = await self._execute_tool(
                tool_name=block.name,
                tool_input=block.input,
                tool_id=block.id,
                messages=messages,
                tools=tools,
            )

            tool_calls.append(ToolCall(
                name=block.name,
                input=block.input,
                output=output,
            ))

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        return results, new_tools

    # ==================== 辅助方法 ====================

    def _sse_event(self, event_type: str, data: dict) -> str:
        """生成 SSE 事件字符串。"""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _extract_text(self, content_blocks) -> str:
        """从 content blocks 中提取文本。"""
        return "".join(
            block.text for block in content_blocks if hasattr(block, "text")
        )


# 全局服务实例
agent_service = AgentService()
