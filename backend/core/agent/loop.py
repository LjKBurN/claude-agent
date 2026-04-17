"""Agent Loop — 核心工具调用循环。

AgentLoop 是 Agent Core 的核心，职责单一：
LLM 调用 → 解析工具调用 → 审批检查 → 执行工具 → 回传结果 → 重复

不了解 SSE、DB 会话、Channel。所有状态通过 EventBus 发出。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.core.agent.approval import ApprovalManager
from backend.core.agent.events import AgentEvent, EventBus, EventType
from backend.core.agent.llm.base import LLMProvider
from backend.core.agent.utils import serialize_blocks
from backend.core.tools.registry import UnifiedToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """工具调用记录（Agent Core 内部使用，不依赖 API 层）。"""
    name: str
    input: dict = field(default_factory=dict)
    output: str = ""

# Agent 执行保护常量
DEFAULT_MAX_ITERATIONS = 20
DEFAULT_TOOL_TIMEOUT = 120
DEFAULT_REQUEST_TIMEOUT = 300  # 5 分钟总超时


@dataclass
class AgentLoopResult:
    """Agent 循环执行的最终结果。"""

    text: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    approval_needed: bool = False
    approval_info: list[dict] | None = None
    content_blocks: list[dict] | None = None
    messages: list[dict] = field(default_factory=list)
    original_count: int = 0


class AgentLoop:
    """核心 Agent 循环。

    与 LLM Provider、SSE 格式、DB 会话完全解耦。
    通过构造函数注入依赖，通过 EventBus 发出事件。
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: UnifiedToolRegistry,
        events: EventBus | None = None,
        approval: ApprovalManager | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        tool_timeout: int = DEFAULT_TOOL_TIMEOUT,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.llm = llm
        self.registry = registry
        self.events = events or EventBus()
        self.approval = approval or ApprovalManager(registry)
        self.max_iterations = max_iterations
        self.tool_timeout = tool_timeout
        self.request_timeout = request_timeout

    async def run(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentLoopResult:
        """运行 Agent 循环直到完成（非流式），带总超时保护。"""
        try:
            return await asyncio.wait_for(
                self._run_impl(messages, system),
                timeout=self.request_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent request timed out ({self.request_timeout}s)")
            await self.events.emit(AgentEvent(
                type=EventType.ERROR,
                data={"message": f"Agent 执行超时 ({self.request_timeout}s)"},
            ))
            return AgentLoopResult(
                text="[Error] Agent 执行超时，请简化请求或稍后重试",
                messages=messages,
            )

    async def _run_impl(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentLoopResult:
        """Agent 循环核心实现（非流式）。"""
        tools = self.registry.anthropic_tools()
        tool_calls: list[ToolCallRecord] = []
        original_count = len(messages)

        for _ in range(self.max_iterations):
            try:
                response = await self.llm.create(messages, tools, system)
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                await self.events.emit(AgentEvent(
                    type=EventType.ERROR,
                    data={"message": f"API 调用失败: {type(e).__name__}"},
                ))
                return AgentLoopResult(
                    text=f"[Error] API 调用失败: {type(e).__name__}",
                    tool_calls=tool_calls,
                    messages=messages,
                    original_count=original_count,
                )

            if response.has_tool_calls():
                # 审批检查
                dangerous = self._filter_dangerous(response.content_blocks, tools)
                if dangerous:
                    return AgentLoopResult(
                        text=response.text,
                        tool_calls=tool_calls,
                        approval_needed=True,
                        approval_info=dangerous,
                        content_blocks=serialize_blocks(response.content_blocks),
                        messages=messages,
                        original_count=original_count,
                    )

                # 执行工具
                messages.append({"role": "assistant", "content": response.content_blocks})
                tool_results = await self._execute_all_tools(
                    response.content_blocks, tool_calls, messages, tools,
                )
                messages.append({"role": "user", "content": tool_results})

            else:
                return AgentLoopResult(
                    text=response.text,
                    tool_calls=tool_calls,
                    messages=messages,
                    original_count=original_count,
                )

        logger.warning(f"Agent reached max iterations ({self.max_iterations})")
        return AgentLoopResult(
            text="[Error] Agent 达到最大工具调用次数，请简化请求",
            tool_calls=tool_calls,
            messages=messages,
            original_count=original_count,
        )

    async def run_stream(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentLoopResult:
        """运行 Agent 循环，通过 EventBus 发出流式事件，带总超时保护。"""
        try:
            return await asyncio.wait_for(
                self._run_stream_impl(messages, system),
                timeout=self.request_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent stream timed out ({self.request_timeout}s)")
            await self.events.emit(AgentEvent(
                type=EventType.ERROR,
                data={"message": f"Agent 执行超时 ({self.request_timeout}s)"},
            ))
            return AgentLoopResult(
                text="[Error] Agent 执行超时，请简化请求或稍后重试",
                messages=messages,
            )

    async def _run_stream_impl(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AgentLoopResult:
        """Agent 流式循环核心实现。"""
        tools = self.registry.anthropic_tools()
        original_count = len(messages)
        tool_calls: list[ToolCallRecord] = []
        full_text = ""

        for _ in range(self.max_iterations):
            try:
                async for chunk in self.llm.create_stream_with_result(messages, tools, system):
                    if chunk.type == "text":
                        full_text += chunk.text
                        await self.events.emit(AgentEvent(
                            type=EventType.TEXT, data={"content": chunk.text},
                        ))
                    elif chunk.type == "tool_start":
                        await self.events.emit(AgentEvent(
                            type=EventType.TOOL_START, data={"name": chunk.tool_name},
                        ))
                    elif chunk.type == "done":
                        pass
            except Exception as e:
                logger.error(f"LLM stream failed: {e}")
                await self.events.emit(AgentEvent(
                    type=EventType.ERROR,
                    data={"message": f"API 调用失败: {type(e).__name__}"},
                ))
                return AgentLoopResult(
                    text=full_text, tool_calls=tool_calls,
                    messages=messages, original_count=original_count,
                )

            # 获取 final_message
            final_message = self.llm.get_last_final_message()
            self.llm.clear_last_final_message()

            if final_message is None:
                return AgentLoopResult(
                    text=full_text, tool_calls=tool_calls,
                    messages=messages, original_count=original_count,
                )

            if final_message.stop_reason == "tool_use":
                # 审批检查
                dangerous = self._filter_dangerous(final_message.content, tools)
                if dangerous:
                    await self.events.emit(AgentEvent(
                        type=EventType.APPROVAL_NEEDED,
                        data={
                            "message": full_text,
                            "tools": dangerous,
                            "content_blocks": serialize_blocks(final_message.content),
                            "messages": messages,
                            "original_count": original_count,
                        },
                    ))
                    return AgentLoopResult(
                        text=full_text, tool_calls=tool_calls,
                        approval_needed=True,
                        approval_info=dangerous,
                        content_blocks=serialize_blocks(final_message.content),
                        messages=messages, original_count=original_count,
                    )

                # 执行工具：先收集所有结果，再一次性 append
                messages.append({"role": "assistant", "content": final_message.content})
                tool_results = []
                for block in final_message.content:
                    if not hasattr(block, "type") or block.type != "tool_use":
                        continue

                    output, extra_events = await self._execute_single_tool(
                        block.name, block.input, block.id, messages, tools,
                    )

                    # 发出额外事件（Skill 加载、MCP 工具注册等）
                    for evt in extra_events:
                        await self.events.emit(evt)
                        if evt.type == EventType.MCP_TOOLS_LOADED:
                            for tool_name in evt.data.get("tools", []):
                                pass  # tools 已在 _execute_single_tool 中扩展

                    await self.events.emit(AgentEvent(
                        type=EventType.TOOL_END,
                        data={"name": block.name, "input": block.input, "output": output},
                    ))

                    tool_calls.append(ToolCallRecord(
                        name=block.name, input=block.input, output=output,
                    ))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })

                # 所有 tool_result 在一条 user 消息中（Anthropic API 要求）
                messages.append({"role": "user", "content": tool_results})

            else:
                return AgentLoopResult(
                    text=full_text, tool_calls=tool_calls,
                    messages=messages, original_count=original_count,
                )

        logger.warning(f"Agent stream reached max iterations ({self.max_iterations})")
        return AgentLoopResult(
            text=full_text + "\n[Error] Agent 达到最大工具调用次数",
            tool_calls=tool_calls,
            messages=messages, original_count=original_count,
        )

    # ==================== 工具执行 ====================

    async def _execute_single_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tool_id: str,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[str, list[AgentEvent]]:
        """执行单个工具调用。

        Returns:
            (output, events) — 工具输出和额外的事件列表
        """
        extra_events: list[AgentEvent] = []

        # 检查是否是 MCP 工具
        mcp_tool_names = {t.name for t in self.registry.by_source("mcp")}

        try:
            if tool_name in mcp_tool_names:
                # MCP 工具直接调用
                from backend.core.mcp.manager import mcp_manager
                output = await asyncio.wait_for(
                    mcp_manager.call_tool(tool_name, tool_input),
                    timeout=self.tool_timeout,
                )
                return output, extra_events

            # 使用 ToolExecutor 执行（内置工具 + Skill + MCP Search）
            from backend.core.tool_executor import tool_executor
            result = tool_executor.execute(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_id=tool_id,
            )

            # Skill 消息注入
            if result.messages_to_inject:
                messages.extend(result.messages_to_inject)
                skill_name = tool_input.get("command", "")
                extra_events.append(AgentEvent(
                    type=EventType.SKILL_LOAD,
                    data={"name": skill_name, "message": f'The "{skill_name}" skill is loading'},
                ))

            # MCP Search 动态工具注册
            if result.tools_to_register and tools is not None:
                tools.extend(result.tools_to_register)
                extra_events.append(AgentEvent(
                    type=EventType.MCP_TOOLS_LOADED,
                    data={
                        "count": len(result.tools_to_register),
                        "tools": [t["name"] for t in result.tools_to_register],
                    },
                ))

            return result.output, extra_events

        except asyncio.TimeoutError:
            return f"Tool '{tool_name}' timed out ({self.tool_timeout}s)", extra_events
        except Exception as e:
            return f"Tool '{tool_name}' failed: {type(e).__name__}: {str(e)[:500]}", extra_events

    async def _execute_all_tools(
        self,
        content_blocks: list[Any],
        tool_calls: list[ToolCallRecord],
        messages: list[dict],
        tools: list[dict],
    ) -> list[dict]:
        """执行所有工具调用块（非流式）。"""
        results = []
        for block in content_blocks:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            output, _ = await self._execute_single_tool(
                block.name, block.input, block.id, messages, tools,
            )
            tool_calls.append(ToolCallRecord(
                name=block.name, input=block.input, output=output,
            ))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        return results

    # ==================== 辅助方法 ====================

    def _filter_dangerous(self, content_blocks: list[Any], tools: list[dict]) -> list[dict]:
        """从 LLM 响应中过滤出需要审批的工具调用。

        同时考虑 MCP 工具白名单（MCP 工具默认安全）。
        """
        dangerous = self.approval.check(content_blocks)
        if not dangerous:
            return dangerous

        # MCP 工具默认安全
        mcp_names = {t.name for t in self.registry.by_source("mcp")}
        return [d for d in dangerous if d["name"] not in mcp_names]

