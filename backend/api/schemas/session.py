"""Session API 请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel


class SessionInfo(BaseModel):
    """会话信息。"""
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionList(BaseModel):
    """会话列表。"""
    sessions: list[SessionInfo]
    total: int


class MessageInfo(BaseModel):
    """消息信息。"""
    id: int
    role: str
    content: str
    created_at: datetime


class MessageList(BaseModel):
    """消息列表。"""
    messages: list[MessageInfo]
    total: int
