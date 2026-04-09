"""上下文管理模块。

提供对话历史的压缩和管理功能，基于 token 数量进行压缩判断。
"""

from backend.core.context.manager import ContextManager, context_manager
from backend.core.context.token_counter import (
    TokenCounter,
    get_token_counter,
    count_tokens,
    count_messages_tokens,
)

__all__ = [
    "ContextManager",
    "context_manager",
    "TokenCounter",
    "get_token_counter",
    "count_tokens",
    "count_messages_tokens",
]
