"""Chat API 请求/响应模型。"""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求。"""
    message: str = Field(..., description="用户消息")
    session_id: str | None = Field(None, description="会话 ID，不传则创建新会话")


class ToolCall(BaseModel):
    """工具调用记录。"""
    name: str
    input: dict[str, Any]
    output: str


class ApprovalInfo(BaseModel):
    """审批信息。"""
    name: str
    input: dict[str, Any]


class ChatResponse(BaseModel):
    """聊天响应。"""
    session_id: str
    message: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    needs_approval: bool = False
    approval_info: list[ApprovalInfo] | None = None
