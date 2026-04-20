"""MCP Server 配置数据模型。"""

import os
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base
from backend.core.mcp.types import MCPServerConfig, TransportType


class MCPServerModel(Base):
    """MCP Server 配置表 — 存储用户配置的 MCP Server。"""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # 传输类型
    transport: Mapped[str] = mapped_column(String(10), default="stdio")  # "stdio" | "http"

    # STDIO 配置
    command: Mapped[str] = mapped_column(String(500), default="")
    args: Mapped[list] = mapped_column(JSON, default=list)
    env: Mapped[dict] = mapped_column(JSON, default=dict)

    # HTTP 配置
    url: Mapped[str] = mapped_column(String(500), default="")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)

    # 控制
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 描述
    description: Mapped[str] = mapped_column(Text, default="")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_config(self) -> MCPServerConfig:
        """转换为 MCPServerConfig dataclass，执行环境变量替换。"""
        # 环境变量替换：${VAR} → os.environ.get(VAR, "")
        processed_env = {}
        for key, value in (self.env or {}).items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                processed_env[key] = os.environ.get(value[2:-1], "")
            else:
                processed_env[key] = value

        processed_headers = {}
        for key, value in (self.headers or {}).items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                processed_headers[key] = os.environ.get(value[2:-1], "")
            else:
                processed_headers[key] = value

        return MCPServerConfig(
            name=self.name,
            transport=TransportType(self.transport),
            command=self.command or "",
            args=self.args or [],
            env=processed_env,
            url=self.url or "",
            headers=processed_headers,
            enabled=self.enabled,
        )
