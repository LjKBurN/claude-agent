"""AgentRunner — Agent 执行逻辑封装。

从 AgentService 提取的 agent 执行层，负责构建 AgentLoop、运行同步/流式调用、
转换 EventBus 事件为 dict 格式。

与 DB、SSE、HTTP 完全解耦，只依赖 Agent Core 组件。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from backend.core.agent.approval import ApprovalManager
from backend.core.agent.events import EventType
from backend.core.agent.llm.base import LLMProvider
from backend.core.agent.loop import AgentLoop, ToolCallRecord
from backend.core.tools.registry import UnifiedToolRegistry

logger = logging.getLogger(__name__)


class AgentRunner:
    """Agent 执行器：构建 AgentLoop 并执行同步/流式调用。

    职责：
    1. 根据 LLM + Registry 构建 AgentLoop
    2. 执行非流式/流式 Agent 循环
    3. 将 EventBus AgentEvent 转换为 dict 格式
    4. 创建 HITL 恢复用的工具执行函数
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: UnifiedToolRegistry,
        max_iterations: int = 20,
        tool_timeout: int = 120,
        request_timeout: int = 300,
    ):
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        self._tool_timeout = tool_timeout
        self._request_timeout = request_timeout

    def _build_loop(self) -> AgentLoop:
        """构建 AgentLoop 实例。"""
        approval = ApprovalManager(tool_lookup=self._registry)
        return AgentLoop(
            llm=self._llm,
            registry=self._registry,
            approval=approval,
            max_iterations=self._max_iterations,
            tool_timeout=self._tool_timeout,
            request_timeout=self._request_timeout,
        )

    async def run(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> tuple[str, list[ToolCallRecord], list[dict] | None, list[dict] | None,
                int, list[dict]]:
        """运行 Agent（非流式）。

        Returns:
            (text, tool_calls, approval_info, content_blocks, original_count, messages)
        """
        loop = self._build_loop()
        result = await loop.run(messages, system_prompt)
        return (
            result.text,
            result.tool_calls,
            result.approval_info,
            result.content_blocks,
            result.original_count,
            result.messages,
        )

    async def run_stream(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> AsyncGenerator[dict, None]:
        """运行 Agent（流式），yield 事件 dict。

        订阅 AgentLoop 的 EventBus，将 AgentEvent 转换为 dict 格式。
        tool_end 事件的 tool_call 字段为 ToolCallRecord（由 AgentService 层转换）。
        """
        loop = self._build_loop()
        queue = loop.events.subscribe_queue()
        loop_task = asyncio.create_task(loop.run_stream(messages, system_prompt))

        try:
            while not loop_task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                # AgentEvent → dict
                if event.type == EventType.TEXT:
                    yield {"type": "text", "content": event.data.get("content", "")}
                elif event.type == EventType.TOOL_START:
                    yield {"type": "tool_start", "name": event.data.get("name", "")}
                elif event.type == EventType.TOOL_END:
                    yield {
                        "type": "tool_end",
                        "tool_call": ToolCallRecord(
                            name=event.data.get("name", ""),
                            input=event.data.get("input", {}),
                            output=event.data.get("output", ""),
                        ),
                    }
                elif event.type == EventType.SKILL_LOAD:
                    yield {
                        "type": "skill_load",
                        "skill_name": event.data.get("name", ""),
                        "message": event.data.get("message", ""),
                    }
                elif event.type == EventType.MCP_TOOLS_LOADED:
                    yield {
                        "type": "mcp_tools_loaded",
                        "count": event.data.get("count", 0),
                        "tools": event.data.get("tools", []),
                    }
                elif event.type == EventType.APPROVAL_NEEDED:
                    yield {
                        "type": "approval_needed",
                        "content_blocks": event.data.get("content_blocks"),
                        "tools": event.data.get("tools"),
                        "messages": event.data.get("messages"),
                        "original_count": event.data.get("original_count"),
                    }
                elif event.type == EventType.ERROR:
                    yield {"type": "text", "content": event.data.get("message", "")}
                elif event.type == EventType.DONE:
                    break
        finally:
            loop.events.unsubscribe_queue(queue)
            if not loop_task.done():
                loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

    def make_tool_executor(self):
        """创建用于 HITL 恢复的工具执行函数。"""
        async def execute_tool(name, input_data, tool_id, messages):
            loop = self._build_loop()
            output, _ = await loop._execute_single_tool(
                name, input_data, tool_id, messages,
            )
            return output
        return execute_tool
