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
    permission: str = "safe"  # "safe" 或 "dangerous"
    check_safe: Callable[[dict], bool] | None = None  # 细粒度权限检查

    def is_safe(self, arguments: dict | None = None) -> bool:
        """判断工具调用是否安全可自动执行。

        Args:
            arguments: 工具参数，用于细粒度判断（如 bash 的具体命令）

        Returns:
            True = 安全，False = 需要审批
        """
        if self.permission == "safe":
            return True
        # dangerous 工具可通过 check_safe 回调细粒度判断
        if self.check_safe and arguments is not None:
            return self.check_safe(arguments)
        return False

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
    permission: str = "safe",
    check_safe: Callable[[dict], bool] | None = None,
) -> Callable:
    """装饰器：注册工具。

    Args:
        permission: "safe"（自动执行）或 "dangerous"（需要审批）
        check_safe: 可选回调，接收 arguments 返回 bool，用于细粒度判断
    """

    def decorator(func: Callable[[dict], str]) -> Callable[[dict], str]:
        tool = Tool(
            name=name,
            description=description,
            handler=func,
            input_schema=input_schema,
            permission=permission,
            check_safe=check_safe,
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
