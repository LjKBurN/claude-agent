"""Agent Hook — 生命周期钩子机制。

在不修改 AgentLoop 核心循环的前提下，通过声明式 Hook 扩展 Agent 行为。

Hook 4 个注入点：
- on_before_llm: LLM 调用前，可修改 messages / system_prompt
- on_after_llm:  LLM 响应后，可审查 / 过滤响应
- on_before_tool: 工具执行前，可修改输入或拒绝执行
- on_after_tool:  工具执行后，可修改输出

典型使用场景：
- KnowledgeRetrievalHook: before_llm 时注入 RAG 上下文到 user message
- LoggingHook: 记录 LLM 调用和工具执行审计日志
- SafetyFilterHook: after_tool 时脱敏敏感信息
- ToolGuardHook: before_tool 时权限控制
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ==================== 核心抽象 ====================

@dataclass
class HookContext:
    """before_llm / after_llm hook 的上下文。

    messages 和 system_prompt 是可变的，hook 可以直接修改。
    """

    messages: list[dict]
    system_prompt: str | None
    iteration: int  # 当前循环轮次（0-based）
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AgentHook(Protocol):
    """Agent 生命周期钩子协议。

    所有方法都有默认实现（no-op），子类只需覆盖关心的方法。
    """

    @property
    def name(self) -> str: ...

    async def on_before_llm(self, ctx: HookContext) -> HookContext:
        return ctx

    async def on_after_llm(self, ctx: HookContext) -> HookContext:
        return ctx

    async def on_before_tool(
        self, tool_name: str, tool_input: dict,
    ) -> dict | None:
        """返回修改后的 input，或 None 表示跳过执行。"""
        return tool_input

    async def on_after_tool(
        self, tool_name: str, tool_input: dict, output: str,
    ) -> str:
        """返回修改后的输出。"""
        return output


# ==================== Hook Runner ====================

async def run_before_llm_hooks(
    hooks: list[Any], ctx: HookContext,
) -> HookContext:
    """依次执行所有 hook 的 on_before_llm。"""
    for hook in hooks:
        try:
            ctx = await hook.on_before_llm(ctx)
        except Exception:
            logger.warning("Hook %s.on_before_llm failed", getattr(hook, "name", "?"),
                           exc_info=True)
    return ctx


async def run_after_llm_hooks(
    hooks: list[Any], ctx: HookContext,
) -> HookContext:
    """依次执行所有 hook 的 on_after_llm。"""
    for hook in hooks:
        try:
            ctx = await hook.on_after_llm(ctx)
        except Exception:
            logger.warning("Hook %s.on_after_llm failed", getattr(hook, "name", "?"),
                           exc_info=True)
    return ctx


async def run_before_tool_hooks(
    hooks: list[Any], tool_name: str, tool_input: dict,
) -> dict | None:
    """依次执行所有 hook 的 on_before_tool。

    返回 None 表示某个 hook 拒绝了该工具调用。
    """
    for hook in hooks:
        try:
            result = await hook.on_before_tool(tool_name, tool_input)
            if result is None:
                return None
            tool_input = result
        except Exception:
            logger.warning("Hook %s.on_before_tool failed", getattr(hook, "name", "?"),
                           exc_info=True)
    return tool_input


async def run_after_tool_hooks(
    hooks: list[Any], tool_name: str, tool_input: dict, output: str,
) -> str:
    """依次执行所有 hook 的 on_after_tool。"""
    for hook in hooks:
        try:
            output = await hook.on_after_tool(tool_name, tool_input, output)
        except Exception:
            logger.warning("Hook %s.on_after_tool failed", getattr(hook, "name", "?"),
                           exc_info=True)
    return output


# ==================== 类型别名 ====================

RetrieveFn = Callable[[str, list[str], int], Awaitable[str]]
"""检索函数签名: (query, kb_ids, top_k) -> formatted_context"""

RewriteFn = Callable[[str, list[dict]], Awaitable[str]]
"""查询改写函数签名: (query, messages) -> rewritten_query"""


# ==================== 内置 Hook ====================

class KnowledgeRetrievalHook:
    """Pre-Retrieval RAG Hook — 在首轮 LLM 调用前自动检索知识库并注入 user message。

    设计要点：
    - 通过 retrieve_fn 注入检索能力，hook 本身不依赖任何基础设施
    - 仅在 iteration == 0 时执行检索（避免后续工具调用轮次浪费计算）
    - 检索结果注入到 user message（不动 system prompt），保证 prompt cache 命中
    - 检索失败静默降级，不阻塞对话
    """

    name: str = "knowledge_retrieval"

    def __init__(
        self,
        knowledge_base_ids: list[str],
        retrieve_fn: RetrieveFn,
        top_k: int = 3,
        rewrite_fn: RewriteFn | None = None,
    ):
        self.knowledge_base_ids = knowledge_base_ids
        self._retrieve_fn = retrieve_fn
        self.top_k = top_k
        self._rewrite_fn = rewrite_fn

    async def on_before_llm(self, ctx: HookContext) -> HookContext:
        # 仅首轮检索
        if ctx.iteration > 0:
            return ctx

        # 提取最后一条用户文本消息
        original_query = self._extract_user_query(ctx.messages)
        if not original_query:
            return ctx

        # 用于检索的 query（可能包含改写内容）
        retrieve_query = original_query

        # Follow-up 检测 + 查询改写（仅配置了知识库时启用）
        if self._rewrite_fn and self._is_followup(ctx.messages):
            try:
                rewritten = await self._rewrite_fn(original_query, ctx.messages)
                if rewritten and rewritten != original_query:
                    logger.info("Follow-up rewrite: %r → %r", original_query, rewritten)
                    # 保留原始 query，拼接改写结果（Elastic 研究表明替换原 query 效果更差）
                    retrieve_query = f"{original_query} {rewritten}"
            except Exception:
                logger.warning("Query rewrite failed, using original", exc_info=True)

        rag_context = await self._pre_retrieve(retrieve_query)
        if not rag_context:
            return ctx

        # 注入到 user message
        self._inject_context(ctx.messages, rag_context)
        return ctx

    # ==================== 内部方法 ====================

    def _extract_user_query(self, messages: list[dict]) -> str:
        """从 messages 中提取最后一条用户文本消息。"""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            # 跳过 tool_result 格式的 user 消息
            if isinstance(content, list):
                # tool_result 消息格式: [{"type": "tool_result", ...}]
                if (content and isinstance(content[0], dict)
                        and content[0].get("type") == "tool_result"):
                    continue
                # 也可能是混合内容，尝试提取文本
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
                continue
            if isinstance(content, str) and content.strip():
                return content.strip()
        return ""

    def _is_followup(self, messages: list[dict]) -> bool:
        """检测当前是否为多轮对话（messages 中存在之前的 assistant 消息）。"""
        for msg in messages:
            if msg.get("role") == "assistant":
                return True
        return False

    async def _pre_retrieve(self, query: str) -> str:
        """委托给注入的 retrieve_fn 执行检索。"""
        try:
            return await self._retrieve_fn(query, self.knowledge_base_ids, self.top_k)
        except Exception:
            logger.warning("KnowledgeRetrievalHook: Pre-Retrieval 失败", exc_info=True)
            return ""

    def _inject_context(self, messages: list[dict], rag_context: str) -> None:
        """将 RAG 上下文注入到最后一条用户文本消息前。"""
        rag_prefix = (
            "<system-reminder>\n"
            "以下是来自知识库的相关内容，可直接用于回答用户问题。\n"
            "如需更多细节，可使用 knowledge_search 工具深入检索。\n\n"
            f"{rag_context}\n"
            "</system-reminder>\n\n"
        )

        # 找到最后一条用户文本消息并注入
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = rag_prefix + content
                return
            if isinstance(content, list):
                # 跳过 tool_result 消息
                if (content and isinstance(content[0], dict)
                        and content[0].get("type") == "tool_result"):
                    continue
                # 在第一个文本 block 前注入
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block["text"] = rag_prefix + block.get("text", "")
                        return
