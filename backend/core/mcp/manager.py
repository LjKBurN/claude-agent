"""MCP Manager。

管理多个 MCP Server 连接，提供统一的工具调用接口。
配置源为数据库（mcp_servers 表），同时保留 .mcp.json 文件加载能力。
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from backend.core.mcp.types import (
    MCPServerConfig,
    MCPTool,
    TransportType,
)
from backend.core.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPManager:
    """MCP Server 管理器。"""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._initialized = False
        self._configs_loaded = False

    # ==================== 配置加载 ====================

    async def load_configs_from_db(self, db_session) -> None:
        """从数据库加载启用的 MCP Server 配置。

        Args:
            db_session: SQLAlchemy async session
        """
        from sqlalchemy import select
        from backend.db.models.mcp_server import MCPServerModel

        result = await db_session.execute(
            select(MCPServerModel).where(MCPServerModel.enabled == True)  # noqa: E712
        )
        models = result.scalars().all()

        self._configs.clear()
        for model in models:
            config = model.to_config()
            self._configs[config.name] = config

        self._configs_loaded = True
        logger.info(f"Loaded {len(self._configs)} MCP server configs from DB")

    def load_config(self, config_path: str | Path) -> None:
        """从 JSON 文件加载配置（Claude Code 格式，用于迁移）。"""
        config_path = Path(config_path)
        if not config_path.exists():
            return

        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        servers = data.get("mcpServers", {})
        for server_name, server_config in servers.items():
            config = self._parse_server_config(server_name, server_config)
            if config:
                self._configs[config.name] = config

    def load_all_configs(self, project_root: str | Path | None = None) -> None:
        """从文件加载所有配置（用于一次性迁移）。"""
        user_config = Path.home() / ".claude.json"
        self.load_config(user_config)

        if project_root:
            project_config = Path(project_root) / ".mcp.json"
        else:
            project_root_auto = Path(__file__).resolve().parent.parent.parent.parent
            project_config = project_root_auto / ".mcp.json"
            if not project_config.exists():
                project_config = Path.cwd() / ".mcp.json"
        self.load_config(project_config)
        self._configs_loaded = True

    def _parse_server_config(self, name: str, data: dict) -> MCPServerConfig | None:
        """解析文件格式的服务器配置。"""
        if not name or not isinstance(data, dict):
            return None

        url = data.get("url", "")
        if url:
            headers = data.get("headers", {})
            processed_headers = {}
            for key, value in headers.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    processed_headers[key] = os.environ.get(value[2:-1], "")
                else:
                    processed_headers[key] = value
            return MCPServerConfig(
                name=name, transport=TransportType.HTTP, url=url,
                headers=processed_headers, command="", args=[], env={},
                enabled=True,
            )

        command = data.get("command", "")
        if not command:
            return None

        env = data.get("env", {})
        processed_env = {}
        for key, value in env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                processed_env[key] = os.environ.get(value[2:-1], "")
            else:
                processed_env[key] = value
        return MCPServerConfig(
            name=name, transport=TransportType.STDIO, command=command,
            args=data.get("args", []), env=processed_env, url="",
            headers={}, enabled=True,
        )

    # ==================== 连接管理（批量） ====================

    async def initialize(self) -> None:
        """初始化所有 MCP 连接。"""
        if self._initialized:
            return

        tasks = []
        for name, config in self._configs.items():
            if name not in self._clients:
                client = MCPClient(config)
                self._clients[name] = client
                tasks.append(self._safe_connect(client))

        await asyncio.gather(*tasks, return_exceptions=True)
        self._initialized = True

    async def _safe_connect(self, client: MCPClient) -> None:
        """安全连接，捕获异常。"""
        try:
            await client.connect()
        except Exception as e:
            client.state.error = str(e)
            logger.warning(f"MCP connect failed for {client.config.name}: {e}")

    async def shutdown(self) -> None:
        """关闭所有连接。"""
        tasks = [client.disconnect() for client in self._clients.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._clients.clear()
        self._initialized = False

    # ==================== 连接管理（单个） ====================

    async def connect_server(self, name: str) -> bool:
        """连接单个 MCP Server。

        Args:
            name: Server 名称

        Returns:
            是否连接成功
        """
        config = self._configs.get(name)
        if not config:
            logger.error(f"MCP server config not found: {name}")
            return False

        # 已存在客户端则先断开
        if name in self._clients:
            await self._clients[name].disconnect()

        client = MCPClient(config)
        self._clients[name] = client
        try:
            await client.connect()
            logger.info(f"MCP server connected: {name}")
            return True
        except Exception as e:
            client.state.error = str(e)
            logger.warning(f"MCP connect failed for {name}: {e}")
            return False

    async def disconnect_server(self, name: str) -> None:
        """断开单个 MCP Server。"""
        client = self._clients.get(name)
        if client:
            await client.disconnect()
            del self._clients[name]
            logger.info(f"MCP server disconnected: {name}")

    async def remove_server(self, name: str) -> None:
        """移除 Server（断开连接 + 移除配置）。"""
        await self.disconnect_server(name)
        self._configs.pop(name, None)

    def update_config(self, name: str, config: MCPServerConfig) -> None:
        """更新 Server 配置。如果已连接需要手动 reconnect。"""
        self._configs[name] = config

    def get_server_details(self, name: str) -> dict | None:
        """获取单个 Server 的详细信息（工具/资源/提示词）。"""
        config = self._configs.get(name)
        if not config:
            return None

        client = self._clients.get(name)
        if client:
            return {
                "name": name,
                "connected": client.is_connected,
                "error": client.state.error,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.input_schema,
                    }
                    for t in client.tools
                ],
                "resources": [
                    {
                        "uri": r.uri,
                        "name": r.name,
                        "description": r.description,
                        "mime_type": r.mime_type,
                    }
                    for r in client.state.resources
                ],
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "arguments": p.arguments,
                    }
                    for p in client.state.prompts
                ],
            }

        return {
            "name": name,
            "connected": False,
            "error": None,
            "tools": [],
            "resources": [],
            "prompts": [],
        }

    # ==================== 工具调用 ====================

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

    def get_tools_for_api(self, servers: list[str] | None = None) -> list[dict]:
        """获取用于 API 的工具列表。"""
        if servers:
            tools = []
            for server_name, client in self._clients.items():
                if server_name in servers and client.is_connected:
                    tools.extend(tool.to_anthropic_format() for tool in client.tools)
            return tools
        return self.get_tools_anthropic_format()

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用工具。"""
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

    # ==================== 状态查询 ====================

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

    def get_configured_servers(self) -> dict:
        """获取所有已配置的服务器信息（无需连接）。"""
        result = {}
        for name in self._configs:
            client = self._clients.get(name)
            if client:
                result[name] = {
                    "connected": client.is_connected,
                    "tools_count": len(client.tools),
                }
            else:
                result[name] = {
                    "connected": False,
                    "tools_count": 0,
                }
        return result


# 全局管理器实例
mcp_manager = MCPManager()
