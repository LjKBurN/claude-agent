"""工具模块。

提供可扩展的工具注册机制，支持动态添加新工具。
"""

# 导入所有工具模块以触发注册
from backend.core.tools import bash, file, http, search, subagent, task  # noqa: F401
from backend.core.tools.base import (
    get_all_tools,
    get_tool,
    get_tools_anthropic_format,
    handle_tool_call,
)
from backend.core.tools.registry import ToolDescriptor


# 兼容旧接口
def get_tools() -> list[dict]:
    """返回可用工具列表（Anthropic 格式）。"""
    return get_tools_anthropic_format()


__all__ = [
    "ToolDescriptor",
    "get_tool",
    "get_all_tools",
    "get_tools",
    "get_tools_anthropic_format",
    "handle_tool_call",
]
