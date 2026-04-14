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
        await self._save_message(db, session.id, "user", user_message)
        messages = await self._get_messages(db, session.id)

        response_text, tool_calls = await self._run_agent(messages)

        await self._save_message(db, session.id, "assistant", response_text)
        await db.commit()

        return ChatResponse(
            session_id=session.id,
            message=response_text,
            tool_calls=tool_calls,
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
        await self._save_message(db, session.id, "user", user_message)
        messages = await self._get_messages(db, session.id)

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
    ) -> tuple[str, list[ToolCall]]:
        """运行 Agent（非流式）。"""
        from anthropic import Anthropic

        client = Anthropic(**self._get_client_kwargs())
        tools = self._get_all_tools()
        tool_calls: list[ToolCall] = []
        system = "You are a helpful assistant."

        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            # API 调用带重试
            try:
                response = await self._call_with_retry(client, messages, tools, system)
            except Exception as e:
                logger.error(f"API call failed after retries: {e}")
                return f"[Error] API 调用失败: {type(e).__name__}", tool_calls

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results, new_tools = await self._process_tool_calls(
                    response.content, tool_calls, messages, tools
                )
                if new_tools:
                    tools.extend(new_tools)
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                text = self._extract_text(response.content)
                return text, tool_calls

            else:
                text = self._extract_text(response.content)
                return text or f"Stopped: {response.stop_reason}", tool_calls

        logger.warning(f"Agent reached max iterations ({MAX_TOOL_ITERATIONS})")
        return "[Error] Agent 达到最大工具调用次数，请简化请求", tool_calls

    async def _run_agent_stream(
        self, messages: list[dict]
    ) -> AsyncGenerator[dict, None]:
        """运行 Agent（流式）。"""
        from anthropic import Anthropic

        client = Anthropic(**self._get_client_kwargs())
        tools = self._get_all_tools()
        system = "You are a helpful assistant."

        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            # API 流式调用带重试
            try:
                stream_ctx = await self._stream_with_retry(client, messages, tools, system)
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
                                    "name": event.content_block.name
                                }

                    elif event.type == "content_block_stop":
                        if current_tool:
                            for evt in await self._process_stream_tool(
                                current_tool, messages, tools
                            ):
                                yield evt
                            current_tool = None

                final_message = stream.get_final_message()

                if final_message.stop_reason == "tool_use":
                    tool_results, new_tools = await self._build_tool_results_from_final(
                        final_message.content
                    )
                    if new_tools:
                        tools.extend(new_tools)
                    messages.append({
                        "role": "assistant",
                        "content": final_message.content
                    })
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

    async def _process_stream_tool(
        self,
        current_tool: dict,
        messages: list[dict],
        tools: list[dict],
    ) -> list[dict]:
        """处理流式工具调用。"""
        try:
            input_data = json.loads(current_tool["input"])
        except json.JSONDecodeError:
            input_data = {}

        output, extra_events = await self._execute_tool(
            tool_name=current_tool["name"],
            tool_input=input_data,
            tool_id=current_tool["id"],
            messages=messages,
            tools=tools,
        )

        events = extra_events or []
        events.append({
            "type": "tool_end",
            "tool_call": ToolCall(
                name=current_tool["name"],
                input=input_data,
                output=output,
            )
        })

        return events

    async def _build_tool_results_from_final(
        self, content_blocks
    ) -> tuple[list[dict], list[dict]]:
        """从 final_message 构建工具结果。

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
                messages=[],
            )

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
