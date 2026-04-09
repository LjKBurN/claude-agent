"""MCP Manager。

管理多个 MCP Server 连接，提供统一的工具调用接口。
配置格式与 Claude Code 兼容（.mcp.json）。
"""

import asyncio
import json
import os
from pathlib import Path

from backend.core.mcp.types import (
    MCPServerConfig,
    MCPTool,
    MCPToolIndexEntry,
    TransportType,
)
from backend.core.mcp.client import MCPClient


class MCPManager:
    """MCP Server 管理器。

    配置加载顺序（后者覆盖前者）：
    1. 用户级：~/.claude.json
    2. 项目级：.mcp.json

    配置格式（与 Claude Code 兼容）：
    {
      "mcpServers": {
        "server-name": {
          "command": "npx",
          "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/path"],
          "env": {"KEY": "value"}
        }
      }
    }

    延迟加载策略：
    - 初始化时只暴露 mcp_search 元工具
    - Claude 搜索后按需加载完整工具定义
    - 大幅减少上下文占用（85-95%）
    """

    # 工具数量阈值，超过此值启用延迟加载
    LAZY_LOAD_THRESHOLD = 10

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._initialized = False
        self._lazy_mode = False  # 是否启用延迟加载模式
        self._loaded_tools: set[str] = set()  # 已加载的完整工具名

    def load_config(self, config_path: str | Path) -> None:
        """从 JSON 文件加载配置（Claude Code 格式）。

        Args:
            config_path: 配置文件路径（.mcp.json 或 ~/.claude.json）
        """
        config_path = Path(config_path)
        if not config_path.exists():
            return

        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        # Claude Code 使用 "mcpServers" 键
        servers = data.get("mcpServers", {})
        for server_name, server_config in servers.items():
            config = self._parse_server_config(server_name, server_config)
            if config:
                self._configs[config.name] = config

    def load_all_configs(self, project_root: str | Path | None = None) -> None:
        """加载所有配置文件。

        加载顺序：
        1. 用户级：~/.claude.json
        2. 项目级：.mcp.json（在项目根目录或当前目录）

        Args:
            project_root: 项目根目录，默认为当前目录
        """
        # 1. 用户级配置
        user_config = Path.home() / ".claude.json"
        self.load_config(user_config)

        # 2. 项目级配置
        if project_root:
            project_config = Path(project_root) / ".mcp.json"
        else:
            project_config = Path.cwd() / ".mcp.json"
        self.load_config(project_config)

    def _parse_server_config(
        self, name: str, data: dict
    ) -> MCPServerConfig | None:
        """解析服务器配置（Claude Code 格式）。

        Claude Code 配置格式：
        {
          "command": "npx" | "uvx" | "python" | ...,
          "args": ["arg1", "arg2"],
          "env": {"KEY": "value"}
        }

        或 HTTP 格式：
        {
          "url": "http://localhost:8080",
          "headers": {"Authorization": "Bearer xxx"}
        }
        """
        if not name or not isinstance(data, dict):
            return None

        # 检查是否是 HTTP transport
        url = data.get("url", "")
        if url:
            # 处理 headers 中的环境变量替换
            headers = data.get("headers", {})
            processed_headers = {}
            for key, value in headers.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    var_name = value[2:-1]
                    processed_headers[key] = os.environ.get(var_name, "")
                else:
                    processed_headers[key] = value

            return MCPServerConfig(
                name=name,
                transport=TransportType.HTTP,
                url=url,
                headers=processed_headers,
                command="",
                args=[],
                env={},
                enabled=True,
            )

        # STDIO transport
        command = data.get("command", "")
        if not command:
            return None

        # 处理环境变量替换
        env = data.get("env", {})
        processed_env = {}
        for key, value in env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                processed_env[key] = os.environ.get(var_name, "")
            else:
                processed_env[key] = value

        return MCPServerConfig(
            name=name,
            transport=TransportType.STDIO,
            command=command,
            args=data.get("args", []),
            env=processed_env,
            url="",
            headers={},
            enabled=True,
        )

    async def initialize(self) -> None:
        """初始化所有 MCP 连接。"""
        if self._initialized:
            return

        # 并行连接所有服务器
        tasks = []
        for name, config in self._configs.items():
            client = MCPClient(config)
            self._clients[name] = client
            tasks.append(self._safe_connect(client))

        # 等待所有连接完成
        await asyncio.gather(*tasks, return_exceptions=True)

        # 检测是否需要启用延迟加载
        total_tools = len(self.get_all_tools())
        self._lazy_mode = total_tools > self.LAZY_LOAD_THRESHOLD

        self._initialized = True

    async def _safe_connect(self, client: MCPClient) -> None:
        """安全连接，捕获异常。"""
        try:
            await client.connect()
        except Exception as e:
            # 连接失败不抛出异常，只记录错误
            client.state.error = str(e)

    async def shutdown(self) -> None:
        """关闭所有连接。"""
        tasks = [client.disconnect() for client in self._clients.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._clients.clear()
        self._initialized = False

    def get_all_tools(self) -> list[MCPTool]:
        """获取所有已连接服务器的工具。"""
        tools = []
        for client in self._clients.values():
            if client.is_connected:
                tools.extend(client.tools)
        return tools

    def get_tools_anthropic_format(self) -> list[dict]:
        """获取 Anthropic 格式的工具列表。"""
        return [tool.to_anthropic_format() for tool in self.get_all_tools()]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        # 查找工具所在的客户端
        for client in self._clients.values():
            if client.is_connected:
                for tool in client.tools:
                    if tool.name == name:
                        try:
                            result = await client.call_tool(name, arguments)
                            return str(result)
                        except Exception as e:
                            return f"Error calling MCP tool {name}: {str(e)}"

        return f"Error: MCP tool not found: {name}"

    def get_connected_servers(self) -> list[str]:
        """获取已连接的服务器列表。"""
        return [
            name for name, client in self._clients.items()
            if client.is_connected
        ]

    def get_server_status(self) -> dict:
        """获取所有服务器状态。"""
        status = {}
        for name, client in self._clients.items():
            status[name] = {
                "connected": client.is_connected,
                "tools_count": len(client.tools),
                "error": client.state.error,
            }
        return status

    # ==================== 延迟加载 ====================

    @property
    def is_lazy_mode(self) -> bool:
        """是否启用延迟加载模式。"""
        return self._lazy_mode

    def get_tool_index(self) -> list[MCPToolIndexEntry]:
        """获取轻量级工具索引。"""
        index = []
        for client in self._clients.values():
            if client.is_connected:
                for tool in client.tools:
                    index.append(tool.to_index_entry())
        return index

    def search_tools(self, query: str) -> list[dict]:
        """搜索 MCP 工具。

        Args:
            query: 搜索关键词

        Returns:
            匹配的工具列表（包含名称、描述、来源服务器）
        """
        query_lower = query.lower()
        results = []

        for entry in self.get_tool_index():
            # 简单的关键词匹配
            if (query_lower in entry.name.lower() or
                query_lower in entry.short_description.lower()):
                results.append({
                    "name": entry.name,
                    "description": entry.short_description,
                    "server": entry.server_name,
                })

        return results

    def get_tool_by_name(self, name: str) -> MCPTool | None:
        """按名称获取完整工具定义（按需加载）。"""
        for client in self._clients.values():
            if client.is_connected:
                for tool in client.tools:
                    if tool.name == name:
                        self._loaded_tools.add(name)
                        return tool
        return None

    def get_tools_by_names(self, names: list[str]) -> list[MCPTool]:
        """按名称列表获取多个工具定义。"""
        tools = []
        for name in names:
            tool = self.get_tool_by_name(name)
            if tool:
                tools.append(tool)
        return tools

    def get_mcp_search_tool_definition(self) -> dict:
        """获取 mcp_search 元工具定义（用于延迟加载模式）。"""
        return {
            "name": "mcp_search",
            "description": (
                "Search for available MCP (Model Context Protocol) tools. "
                "Use this when you need to access external resources like "
                "databases, file systems, or APIs. Returns a list of matching "
                "tools with their descriptions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing the tool you need",
                    },
                },
                "required": ["query"],
            },
        }

    def get_tools_for_api(self) -> tuple[list[dict], bool]:
        """获取用于 API 的工具列表。

        Returns:
            (tools_list, used_lazy_mode)
            - tools_list: 工具定义列表
            - used_lazy_mode: 是否使用了延迟加载模式
        """
        if self._lazy_mode:
            # 延迟加载模式：只返回 mcp_search 元工具
            return [self.get_mcp_search_tool_definition()], True
        else:
            # 直接模式：返回所有工具
            return self.get_tools_anthropic_format(), False


# 全局管理器实例
mcp_manager = MCPManager()
