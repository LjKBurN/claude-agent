"""MCP (Model Context Protocol) 模块。

作为 MCP Host 连接外部 MCP Server，扩展 Agent 能力。
"""

from backend.core.mcp.types import (
    MCPServerConfig,
    MCPTool,
    MCPResource,
    MCPPrompt,
)
from backend.core.mcp.manager import mcp_manager

__all__ = [
    "MCPServerConfig",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    "mcp_manager",
]
