"""工具基础类型和注册机制。

@register_tool 装饰器将工具直接注册到模块级 UnifiedToolRegistry 单例中，
消除 base.py 与 registry.py 之间的双重状态。
"""

from __future__ import annotations

from typing import Callable

from backend.core.tools.registry import ToolDescriptor, UnifiedToolRegistry

# 模块级内置工具注册表单例
_builtin_registry = UnifiedToolRegistry()


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    permission: str = "safe",
    check_safe: Callable[[dict], bool] | None = None,
) -> Callable:
    """装饰器：注册工具。

    Args:
        permission: "safe"（自动执行）或 "dangerous"（需要审批）
        check_safe: 可选回调，接收 arguments 返回 bool，用于细粒度判断
    """

    def decorator(func: Callable[[dict], str]) -> Callable[[dict], str]:
        _builtin_registry.register(ToolDescriptor(
            name=name,
            description=description,
            input_schema=input_schema,
            source="builtin",
            permission=permission,
            check_safe=check_safe,
            handler=func,
        ))
        return func

    return decorator


def get_tool(name: str) -> ToolDescriptor | None:
    """获取工具。"""
    return _builtin_registry.get(name)


def get_all_tools() -> list[ToolDescriptor]:
    """获取所有工具。"""
    return _builtin_registry.all_tools()


def get_tools_anthropic_format() -> list[dict]:
    """获取 Anthropic 格式的工具列表。"""
    return _builtin_registry.anthropic_tools()


def handle_tool_call(name: str, arguments: dict) -> str:
    """处理工具调用并返回结果。"""
    tool = _builtin_registry.get(name)
    if tool and tool.handler:
        return tool.handler(arguments)
    return f"Unknown tool: {name}"
