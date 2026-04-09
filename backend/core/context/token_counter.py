"""Token 计算工具。

支持多种模型的 token 计算和上下文预算管理。
"""

import json
from functools import lru_cache
from typing import Any

import tiktoken


class TokenCounter:
    """Token 计算器。

    支持计算消息列表的 token 数量，用于上下文管理。
    """

    # Claude 模型使用 cl100k_base 编码（与 GPT-4 相同）
    DEFAULT_ENCODING = "cl100k_base"

    # Claude 模型的上下文窗口大小
    MODEL_CONTEXT_LIMITS = {
        "claude-opus-4-6": 200000,
        "claude-sonnet-4-6": 200000,
        "claude-sonnet-4-5": 200000,
        "claude-haiku-4-5": 200000,
        "claude-3-5-sonnet": 200000,
        "claude-3-5-haiku": 200000,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
    }

    # 默认上下文限制
    DEFAULT_CONTEXT_LIMIT = 200000

    # 消息格式的额外 token 开销（role、结构等）
    MESSAGE_OVERHEAD_TOKENS = 4

    def __init__(self, model_id: str | None = None):
        """初始化 Token 计算器。

        Args:
            model_id: 模型 ID，用于确定上下文限制
        """
        self.encoding = tiktoken.get_encoding(self.DEFAULT_ENCODING)
        self.model_id = model_id
        self.context_limit = self._get_context_limit(model_id)

    def _get_context_limit(self, model_id: str | None) -> int:
        """获取模型的上下文限制。"""
        if not model_id:
            return self.DEFAULT_CONTEXT_LIMIT

        # 尝试精确匹配
        if model_id in self.MODEL_CONTEXT_LIMITS:
            return self.MODEL_CONTEXT_LIMITS[model_id]

        # 尝试前缀匹配
        for key, limit in self.MODEL_CONTEXT_LIMITS.items():
            if model_id.startswith(key) or key.startswith(model_id.split("-")[0]):
                return limit

        return self.DEFAULT_CONTEXT_LIMIT

    def count_text_tokens(self, text: str) -> int:
        """计算文本的 token 数量。

        Args:
            text: 要计算的文本

        Returns:
            token 数量
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_message_tokens(self, message: dict[str, Any]) -> int:
        """计算单条消息的 token 数量。

        包括：
        - role 字段
        - content 字段（字符串或结构化内容）
        - 消息格式的开销

        Args:
            message: 消息字典，包含 role 和 content

        Returns:
            token 数量
        """
        total = self.MESSAGE_OVERHEAD_TOKENS

        # 计算 role 的 token
        role = message.get("role", "")
        total += self.count_text_tokens(role)

        # 计算 content 的 token
        content = message.get("content")
        if content is None:
            pass
        elif isinstance(content, str):
            total += self.count_text_tokens(content)
        elif isinstance(content, list):
            # 结构化内容（多模态或 tool_use）
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        total += self.count_text_tokens(block.get("text", ""))
                    elif block_type == "tool_use":
                        total += self.count_text_tokens(block.get("name", ""))
                        total += self.count_text_tokens(
                            json.dumps(block.get("input", {}), ensure_ascii=False)
                        )
                    elif block_type == "tool_result":
                        total += self.count_text_tokens(block.get("content", ""))
                    elif block_type == "image":
                        # 图像 token 估算（简化处理）
                        total += 85  # 小图的近似值
                elif isinstance(block, str):
                    total += self.count_text_tokens(block)

        # 计算 name 字段（如果有）
        name = message.get("name")
        if name:
            total += self.count_text_tokens(name)

        return total

    def count_messages_tokens(self, messages: list[dict[str, Any]]) -> int:
        """计算消息列表的总 token 数量。

        Args:
            messages: 消息列表

        Returns:
            总 token 数量
        """
        return sum(self.count_message_tokens(msg) for msg in messages)

    def get_token_budget_info(
        self,
        messages: list[dict[str, Any]],
        reserve_for_response: int = 8000,
    ) -> dict[str, Any]:
        """获取 token 预算信息。

        Args:
            messages: 当前消息列表
            reserve_for_response: 为响应保留的 token 数量

        Returns:
            预算信息字典
        """
        used_tokens = self.count_messages_tokens(messages)
        available = self.context_limit - used_tokens - reserve_for_response

        return {
            "used_tokens": used_tokens,
            "context_limit": self.context_limit,
            "reserve_for_response": reserve_for_response,
            "available_tokens": max(0, available),
            "usage_percentage": round(used_tokens / self.context_limit * 100, 2),
            "should_compress": available < reserve_for_response,
        }

    def fit_messages_to_budget(
        self,
        messages: list[dict[str, Any]],
        budget: int,
        keep_first: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """在 token 预算内截断消息。

        Args:
            messages: 消息列表
            budget: token 预算
            keep_first: 保留的前几条消息（通常是系统消息）

        Returns:
            (截断后的消息列表, 截断的 token 数量)
        """
        if not messages:
            return [], 0

        # 分离要保留的前几条消息和其余消息
        first_messages = messages[:keep_first]
        rest_messages = messages[keep_first:]

        # 计算保留消息的 token
        first_tokens = self.count_messages_tokens(first_messages)
        remaining_budget = budget - first_tokens

        if remaining_budget <= 0:
            # 预算不足以保留前几条消息
            return first_messages, self.count_messages_tokens(messages) - first_tokens

        # 从最新消息开始，逆向累积
        result = []
        current_tokens = 0

        for msg in reversed(rest_messages):
            msg_tokens = self.count_message_tokens(msg)
            if current_tokens + msg_tokens <= remaining_budget:
                result.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 预算用尽，停止添加
                break

        final_messages = first_messages + result
        truncated_tokens = self.count_messages_tokens(messages) - self.count_messages_tokens(final_messages)

        return final_messages, truncated_tokens


@lru_cache
def get_token_counter(model_id: str | None = None) -> TokenCounter:
    """获取 TokenCounter 实例（带缓存）。"""
    return TokenCounter(model_id)


def count_tokens(text: str, model_id: str | None = None) -> int:
    """快捷方法：计算文本的 token 数量。"""
    counter = get_token_counter(model_id)
    return counter.count_text_tokens(text)


def count_messages_tokens(
    messages: list[dict[str, Any]],
    model_id: str | None = None,
) -> int:
    """快捷方法：计算消息列表的 token 数量。"""
    counter = get_token_counter(model_id)
    return counter.count_messages_tokens(messages)
