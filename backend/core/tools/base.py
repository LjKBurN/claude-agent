"""工具基础类型和注册机制。"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Tool:
    """工具定义。"""

    name: str
    description: str
    handler: Callable[[dict], str]
    input_schema: dict = field(default_factory=dict)

    def to_anthropic_format(self) -> dict:
        """转换为 Anthropic API 格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


# 全局工具注册表
_registry: dict[str, Tool] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
) -> Callable:
    """装饰器：注册工具。"""

    def decorator(func: Callable[[dict], str]) -> Callable[[dict], str]:
        tool = Tool(
            name=name,
            description=description,
            handler=func,
            input_schema=input_schema,
        )
        _registry[name] = tool
        return func

    return decorator


def get_tool(name: str) -> Tool | None:
    """获取工具。"""
    return _registry.get(name)


def get_all_tools() -> list[Tool]:
    """获取所有工具。"""
    return list(_registry.values())


def get_tools_anthropic_format() -> list[dict]:
    """获取 Anthropic 格式的工具列表。"""
    return [tool.to_anthropic_format() for tool in _registry.values()]


def handle_tool_call(name: str, arguments: dict) -> str:
    """
    处理工具调用并返回结果。

    Args:
        name: 要调用的工具名称
        arguments: 传递给工具的参数

    Returns:
        工具调用的结果
    """
    tool = get_tool(name)
    if tool:
        return tool.handler(arguments)
    return f"Unknown tool: {name}"
