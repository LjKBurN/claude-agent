"""查询改写 — 利用对话历史将 follow-up query 转为完整独立查询。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

REWRITE_SYSTEM_PROMPT = (
    "你是一个查询改写助手。根据对话历史，将用户的追问改写为完整的独立查询。\n"
    "规则：保留原始意图，补充必要的上下文信息，输出简洁的改写查询，不要解释。\n"
    "如果查询已经是完整的独立查询，直接原样返回。"
)

REWRITE_USER_TEMPLATE = (
    "对话历史：\n{context}\n\n当前问题：{query}\n\n改写后的查询："
)

# 从 messages 中提取对话上下文时的最大轮数
_MAX_CONTEXT_TURNS = 3


class QueryRewriter:
    """使用 LLM 改写 follow-up 查询。

    失败时静默降级，返回原始 query。
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """延迟创建 Anthropic async client。"""
        if self._client is None:
            import anthropic

            from backend.config import get_settings

            settings = get_settings()
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url or None,
            )
        return self._client

    async def rewrite(self, query: str, conversation_context: str) -> str:
        """改写 follow-up 查询。

        Args:
            query: 原始查询。
            conversation_context: 对话历史文本。

        Returns:
            改写后的查询，失败时返回原始 query。
        """
        if not conversation_context:
            return query

        client = self._get_client()
        user_msg = REWRITE_USER_TEMPLATE.format(context=conversation_context, query=query)

        try:
            from backend.config import get_settings

            response = await client.messages.create(
                model=get_settings().model_id,
                max_tokens=100,
                system=REWRITE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            rewritten = response.content[0].text.strip()
            if rewritten:
                logger.info("Query rewrite: %r → %r", query, rewritten)
                return rewritten
            return query
        except Exception:
            logger.warning("Query rewrite failed, using original query", exc_info=True)
            return query

    async def rewrite_with_messages(self, query: str, messages: list[dict]) -> str:
        """从 messages 列表提取上下文并改写查询。

        Args:
            query: 原始查询。
            messages: 完整的消息列表。

        Returns:
            改写后的查询。
        """
        context = extract_conversation_context(messages)
        if not context:
            return query
        return await self.rewrite(query, context)


def extract_conversation_context(messages: list[dict]) -> str:
    """从消息列表中提取最近几轮对话文本。

    跳过 tool_result 消息和 RAG 注入的 system-reminder 内容。
    只保留 user 和 assistant 的文本消息。

    Returns:
        格式化的对话历史文本，如 "用户: xxx\n助手: xxx"
    """
    turns: list[str] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        # 只取 user 和 assistant 消息
        if role not in ("user", "assistant"):
            continue

        # 提取文本内容
        text = _extract_text_from_content(content)
        if not text:
            continue

        # 跳过 RAG 注入的上下文（以 <system-reminder> 开头）
        if "<system-reminder>" in text:
            # 去掉 system-reminder 块，只保留用户原始消息
            text = _strip_rag_context(text)
            if not text:
                continue

        label = "用户" if role == "user" else "助手"
        turns.append(f"{label}: {text}")

    # 取最近 N 轮（不包括最后一轮，因为最后一轮就是当前 query）
    if len(turns) <= 1:
        return ""

    # 去掉最后一轮（当前 query），保留之前的上下文
    context_turns = turns[-_MAX_CONTEXT_TURNS - 1 : -1]
    if not context_turns:
        return ""

    return "\n".join(context_turns)


def _extract_text_from_content(content) -> str:
    """从消息 content 中提取纯文本。"""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        # 跳过 tool_result 消息
        if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
            return ""
        # 拼接所有文本块
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts).strip()
    return ""


def _strip_rag_context(text: str) -> str:
    """去掉 RAG 注入的 <system-reminder>...</system-reminder> 块。"""
    import re

    return re.sub(r"<system-reminder>.*?</system-reminder>\n*", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_instance: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    """获取 QueryRewriter 单例。"""
    global _instance
    if _instance is None:
        _instance = QueryRewriter()
    return _instance
