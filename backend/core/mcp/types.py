"""MCP 类型定义。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TransportType(str, Enum):
    """MCP 传输类型。"""

    STDIO = "stdio"
    HTTP = "http"


# ==================== JSON-RPC 消息类型 ====================


@dataclass
class JSONRPCMessage:
    """JSON-RPC 2.0 消息。"""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str | None = None
    params: dict | None = None
    result: Any = None
    error: dict | None = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        d = {"jsonrpc": "2.0"}
        if self.id is not None:
            d["id"] = self.id
        if self.method:
            d["method"] = self.method
        if self.params is not None:
            d["params"] = self.params
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "JSONRPCMessage":
        """从字典创建。"""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )


# ==================== Transport 基类 ====================


class BaseTransport(ABC):
    """MCP Transport 抽象基类。"""

    def __init__(self, config: "MCPServerConfig"):
        self.config = config

    @abstractmethod
    async def start(self) -> None:
        """启动传输层连接。"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止传输层连接。"""
        pass

    @abstractmethod
    async def send_request(
        self,
        method: str,
        params: dict | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """发送请求并等待响应。"""
        pass

    @abstractmethod
    async def send_notification(self, method: str, params: dict | None = None) -> None:
        """发送通知（不等待响应）。"""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """检查连接是否活跃。"""
        pass


# ==================== MCP 配置和类型 ====================


@dataclass
class MCPServerConfig:
    """MCP Server 配置。"""

    name: str  # Server 名称（用于标识）
    transport: TransportType = TransportType.STDIO

    # STDIO 配置
    command: str = ""  # 可执行命令
    args: list[str] = field(default_factory=list)  # 命令参数
    env: dict[str, str] = field(default_factory=dict)  # 环境变量

    # HTTP/SSE 配置
    url: str = ""  # HTTP URL（如 http://localhost:8080）
    headers: dict[str, str] = field(default_factory=dict)  # HTTP headers

    # 其他配置
    enabled: bool = True  # 是否启用


@dataclass
class MCPTool:
    """MCP Tool 定义。"""

    name: str  # 工具名称
    description: str  # 工具描述
    input_schema: dict[str, Any]  # 输入 schema

    # 元数据
    server_name: str = ""  # 来源 Server

    def to_anthropic_format(self) -> dict:
        """转换为 Anthropic API 工具格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class MCPResource:
    """MCP Resource 定义。"""

    uri: str  # 资源 URI
    name: str  # 资源名称
    description: str = ""
    mime_type: str = ""

    # 元数据
    server_name: str = ""


@dataclass
class MCPPrompt:
    """MCP Prompt 定义。"""

    name: str  # Prompt 名称
    description: str = ""
    arguments: list[dict] = field(default_factory=list)

    # 元数据
    server_name: str = ""


@dataclass
class MCPConnectionState:
    """MCP 连接状态。"""

    server_name: str
    connected: bool = False
    capabilities: dict[str, Any] = field(default_factory=dict)
    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)
    prompts: list[MCPPrompt] = field(default_factory=list)
    error: str | None = None


