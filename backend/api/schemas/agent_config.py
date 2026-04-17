"""Agent Config API 请求/响应模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateAgentConfigRequest(BaseModel):
    """创建 Agent 配置请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="Agent 名称")
    description: str = Field("", max_length=500, description="Agent 描述")

    # LLM 配置
    model_id: str = Field("claude-sonnet-4-6-20250514", description="模型 ID")
    max_tokens: int = Field(8000, ge=100, le=64000, description="最大 token 数")

    # 工具配置
    builtin_tools: list[str] = Field(
        default_factory=list, description="启用的内置工具列表，空=全部"
    )
    include_skills: bool = Field(True, description="是否启用 Skills")
    include_mcp: bool = Field(True, description="是否启用 MCP")
    mcp_servers: list[str] = Field(
        default_factory=list, description="启用的 MCP Server，空=全部"
    )

    # 行为
    max_iterations: int = Field(20, ge=1, le=100, description="最大工具迭代次数")
    tool_timeout: int = Field(120, ge=10, le=600, description="工具执行超时（秒）")
    auto_approve_safe: bool = Field(True, description="安全工具自动批准")

    # 自定义
    system_prompt_overrides: dict[str, str] = Field(
        default_factory=dict, description="System Prompt 覆盖"
    )

    # 元数据
    avatar: str | None = Field(None, max_length=50, description="头像标识")


class UpdateAgentConfigRequest(BaseModel):
    """更新 Agent 配置请求。"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    model_id: str | None = None
    max_tokens: int | None = Field(None, ge=100, le=64000)
    builtin_tools: list[str] | None = None
    include_skills: bool | None = None
    include_mcp: bool | None = None
    mcp_servers: list[str] | None = None
    max_iterations: int | None = Field(None, ge=1, le=100)
    tool_timeout: int | None = Field(None, ge=10, le=600)
    auto_approve_safe: bool | None = None
    system_prompt_overrides: dict[str, str] | None = None
    avatar: str | None = Field(None, max_length=50)


class AgentConfigInfo(BaseModel):
    """Agent 配置详情。"""

    id: str
    name: str
    description: str
    model_id: str
    max_tokens: int
    builtin_tools: list[str]
    include_skills: bool
    include_mcp: bool
    mcp_servers: list[str]
    max_iterations: int
    tool_timeout: int
    auto_approve_safe: bool
    system_prompt_overrides: dict[str, str]
    avatar: str | None
    created_at: datetime
    updated_at: datetime


class AgentConfigList(BaseModel):
    """Agent 配置列表。"""

    configs: list[AgentConfigInfo]
    total: int


class ToolInfo(BaseModel):
    """工具信息。"""

    name: str
    description: str
    source: str  # "builtin" | "skill" | "mcp"
    permission: str  # "safe" | "dangerous"


class ToolsListResponse(BaseModel):
    """工具列表响应。"""

    tools: list[ToolInfo]
    builtin: list[ToolInfo]
    mcp: list[ToolInfo]
