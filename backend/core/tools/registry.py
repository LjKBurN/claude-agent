"""统一工具注册表。

将内置工具、Skill meta-tool、MCP 工具聚合到统一的查询接口，
替代分散在 tools/base.py、skills/registry.py、mcp/manager.py 中的工具发现逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDescriptor:
    """所有工具源的统一描述符。"""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    source: str = "builtin"  # "builtin" | "skill" | "mcp"
    permission: str = "safe"  # "safe" | "dangerous"
    check_safe: Callable[[dict], bool] | None = None
    handler: Callable[[dict], str] | None = None  # 内置工具的执行函数

    def to_anthropic_format(self) -> dict:
        """转换为 Anthropic API 工具定义格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def is_safe(self, arguments: dict | None = None) -> bool:
        """判断工具调用是否安全可自动执行。"""
        if self.permission == "safe":
            return True
        if self.check_safe and arguments is not None:
            return self.check_safe(arguments)
        return False


class UnifiedToolRegistry:
    """将所有工具源聚合到一个查询接口。

    用法：
        registry = UnifiedToolRegistry()
        registry.register(ToolDescriptor(name="bash", ...))

        # 获取 Anthropic API 格式的工具列表
        tools = registry.anthropic_tools()

        # 检查工具安全性
        safe = registry.is_safe("bash", {"command": "rm -rf /"})
    """

    def __init__(self):
        self._tools: dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        """注册一个工具描述符。"""
        self._tools[descriptor.name] = descriptor

    def register_batch(self, descriptors: list[ToolDescriptor]) -> None:
        """批量注册工具描述符。"""
        for desc in descriptors:
            self._tools[desc.name] = desc

    def unregister(self, name: str) -> None:
        """注销一个工具。"""
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDescriptor | None:
        """获取工具描述符。"""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """检查工具是否已注册。"""
        return name in self._tools

    def all_tools(self) -> list[ToolDescriptor]:
        """获取所有工具描述符。"""
        return list(self._tools.values())

    def anthropic_tools(self) -> list[dict]:
        """获取 Anthropic API 格式的工具列表。"""
        return [t.to_anthropic_format() for t in self._tools.values()]

    def is_safe(self, name: str, arguments: dict | None = None) -> bool:
        """检查工具是否安全可自动执行。"""
        tool = self._tools.get(name)
        if tool:
            return tool.is_safe(arguments)
        return False

    def by_source(self, source: str) -> list[ToolDescriptor]:
        """按来源过滤工具。"""
        return [t for t in self._tools.values() if t.source == source]

    def snapshot(self) -> UnifiedToolRegistry:
        """创建一个可变副本。

        用于 Agent 循环中动态注册 MCP 工具时，
        不影响原始注册表。
        """
        new = UnifiedToolRegistry()
        new._tools = dict(self._tools)
        return new

    @property
    def tool_names(self) -> set[str]:
        """获取所有工具名称。"""
        return set(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def populate_registry(
    builtin_only: list[str] | None = None,
    skills: list[str] | None = None,
    mcp_servers: list[str] | None = None,
) -> UnifiedToolRegistry:
    """从所有工具源填充统一注册表。

    Args:
        builtin_only: None = 全部内置工具; [] = 无内置工具; 非空列表 = 指定的内置工具
        skills: None = 全部 skills; [] = 无 skills; 非空列表 = 指定的 skills
        mcp_servers: None = 全部 MCP; [] = 无 MCP; 非空列表 = 指定的 MCP servers

    Returns:
        填充好的 UnifiedToolRegistry
    """
    from backend.core.tools.base import _builtin_registry

    registry = UnifiedToolRegistry()

    # 1. 内置工具
    for desc in _builtin_registry.all_tools():
        if builtin_only is not None and desc.name not in builtin_only:
            continue
        registry.register(desc)

    # 2. Skill meta-tool (None = 全部, [] = 不注册, 非空 = 指定)
    if skills is None or len(skills) > 0:
        try:
            from backend.core.skills.registry import skill_registry
            skill_def = skill_registry.get_skill_tool_definition()
            if skill_def:
                registry.register(ToolDescriptor(
                    name=skill_def["name"],
                    description=skill_def["description"],
                    input_schema=skill_def["input_schema"],
                    source="skill",
                ))
        except Exception:
            pass  # Skills 可能未配置

    # 3. MCP 工具
    if mcp_servers is None or len(mcp_servers) > 0:
        try:
            from backend.core.mcp.manager import mcp_manager
            mcp_tools = mcp_manager.get_tools_for_api(mcp_servers)
            for mt in mcp_tools:
                registry.register(ToolDescriptor(
                    name=mt["name"],
                    description=mt.get("description", ""),
                    input_schema=mt.get("input_schema", {}),
                    source="mcp",
                ))
        except Exception:
            pass  # MCP 可能未初始化

    return registry
