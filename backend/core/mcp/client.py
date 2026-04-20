"""MCP Client 实现。

管理与单个 MCP Server 的连接和交互。
"""

from typing import Any

from backend.core.mcp.types import (
    MCPServerConfig,
    MCPTool,
    MCPResource,
    MCPPrompt,
    MCPConnectionState,
    TransportType,
)
from backend.core.mcp.transport.stdio import STDIOTransport
from backend.core.mcp.transport.http import HTTPTransport


class MCPClient:
    """MCP Client。

    管理与单个 MCP Server 的连接，提供工具/资源/提示的访问。
    支持 STDIO 和 HTTP/SSE 两种传输方式。
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.transport = self._create_transport(config)
        self.state = MCPConnectionState(server_name=config.name)

    def _create_transport(self, config: MCPServerConfig):
        """根据配置创建对应的传输层。"""
        if config.transport == TransportType.HTTP:
            return HTTPTransport(config)
        else:
            return STDIOTransport(config)

    async def connect(self) -> bool:
        """连接到 MCP Server 并初始化。"""
        try:
            # 启动传输层
            await self.transport.start()

            # 初始化握手
            result = await self.transport.send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {},
                    },
                    "clientInfo": {
                        "name": "claude-agent",
                        "version": "1.0.0",
                    },
                },
            )

            # 保存服务器能力
            self.state.capabilities = result.get("capabilities", {})

            # 发送 initialized 通知
            await self.transport.send_notification("notifications/initialized")

            self.state.connected = True
            self.state.error = None

            # 获取可用工具/资源/提示
            await self._load_capabilities()

            return True

        except Exception as e:
            self.state.connected = False
            self.state.error = str(e)
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """断开连接。"""
        await self.transport.stop()
        self.state.connected = False

    async def _load_capabilities(self) -> None:
        """加载服务器提供的工具/资源/提示。"""
        # 加载工具
        if self._has_capability("tools"):
            try:
                result = await self.transport.send_request("tools/list", {})
                for tool_data in result.get("tools", []):
                    self.state.tools.append(MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        server_name=self.config.name,
                    ))
            except Exception:
                pass

        # 加载资源
        if self._has_capability("resources"):
            try:
                result = await self.transport.send_request("resources/list", {})
                for res_data in result.get("resources", []):
                    self.state.resources.append(MCPResource(
                        uri=res_data["uri"],
                        name=res_data.get("name", ""),
                        description=res_data.get("description", ""),
                        mime_type=res_data.get("mimeType", ""),
                        server_name=self.config.name,
                    ))
            except Exception:
                pass

        # 加载提示
        if self._has_capability("prompts"):
            try:
                result = await self.transport.send_request("prompts/list", {})
                for prompt_data in result.get("prompts", []):
                    self.state.prompts.append(MCPPrompt(
                        name=prompt_data["name"],
                        description=prompt_data.get("description", ""),
                        arguments=prompt_data.get("arguments", []),
                        server_name=self.config.name,
                    ))
            except Exception:
                pass

    def _has_capability(self, capability: str) -> bool:
        """检查服务器是否支持某个能力。"""
        return capability in self.state.capabilities

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具。"""
        if not self.state.connected:
            raise RuntimeError(f"Not connected to MCP server: {self.config.name}")

        result = await self.transport.send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

        # 提取内容
        content = result.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    # 将图片转为 data URL，前端可渲染为 <img>
                    mime = item.get("mimeType", "image/png")
                    data = item.get("data", "")
                    if data:
                        parts.append(f"data:{mime};base64,{data}")
            return "\n".join(parts) if parts else str(result)

        return result

    async def read_resource(self, uri: str) -> Any:
        """读取资源。"""
        if not self.state.connected:
            raise RuntimeError(f"Not connected to MCP server: {self.config.name}")

        result = await self.transport.send_request(
            "resources/read",
            {"uri": uri},
        )

        return result

    async def get_prompt(self, name: str, arguments: dict | None = None) -> Any:
        """获取提示。"""
        if not self.state.connected:
            raise RuntimeError(f"Not connected to MCP server: {self.config.name}")

        result = await self.transport.send_request(
            "prompts/get",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

        return result

    @property
    def tools(self) -> list[MCPTool]:
        """获取可用工具列表。"""
        return self.state.tools

    @property
    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.state.connected
