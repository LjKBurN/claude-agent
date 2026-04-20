"""MCP Server API 请求/响应模型。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CreateMCPServerRequest(BaseModel):
    """创建 MCP Server 请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="Server 名称")
    transport: Literal["stdio", "http"] = Field("stdio", description="传输类型")
    # STDIO
    command: str = Field("", max_length=500, description="可执行命令 (stdio)")
    args: list[str] = Field(default_factory=list, description="命令参数 (stdio)")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量，支持 ${VAR} 语法")
    # HTTP
    url: str = Field("", max_length=500, description="HTTP URL (http)")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP 请求头 (http)")
    # 控制
    enabled: bool = Field(True, description="是否启用")
    description: str = Field("", max_length=500, description="描述")

    @model_validator(mode="after")
    def validate_transport_fields(self):
        if self.transport == "stdio" and not self.command:
            raise ValueError("STDIO transport requires 'command'")
        if self.transport == "http" and not self.url:
            raise ValueError("HTTP transport requires 'url'")
        return self


class UpdateMCPServerRequest(BaseModel):
    """更新 MCP Server 请求。"""

    name: str | None = Field(None, min_length=1, max_length=100)
    transport: Literal["stdio", "http"] | None = None
    command: str | None = Field(None, max_length=500)
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = Field(None, max_length=500)
    headers: dict[str, str] | None = None
    enabled: bool | None = None
    description: str | None = Field(None, max_length=500)


class MCPServerInfo(BaseModel):
    """MCP Server 配置详情。"""

    id: str
    name: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, str]
    url: str
    headers: dict[str, str]
    enabled: bool
    description: str
    created_at: datetime
    updated_at: datetime


class MCPServerList(BaseModel):
    """MCP Server 列表。"""

    servers: list[MCPServerInfo]
    total: int


class MCPToolInfo(BaseModel):
    """MCP 工具信息。"""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPResourceInfo(BaseModel):
    """MCP 资源信息。"""

    uri: str
    name: str
    description: str
    mime_type: str


class MCPPromptInfo(BaseModel):
    """MCP 提示词信息。"""

    name: str
    description: str
    arguments: list[dict[str, Any]]


class MCPServerStatusInfo(BaseModel):
    """MCP Server 实时状态。"""

    name: str
    connected: bool
    error: str | None = None
    tools: list[MCPToolInfo] = []
    resources: list[MCPResourceInfo] = []
    prompts: list[MCPPromptInfo] = []
