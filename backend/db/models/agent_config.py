"""Agent 配置数据模型。"""

from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class AgentConfigModel(Base):
    """Agent 配置表 — 存储用户自定义的 Agent 配置。"""

    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # LLM 配置
    model_id: Mapped[str] = mapped_column(
        String(100), default="claude-sonnet-4-6-20250514"
    )
    max_tokens: Mapped[int] = mapped_column(Integer, default=8000)

    # 工具配置 (JSON)
    builtin_tools: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    mcp_servers: Mapped[list] = mapped_column(JSON, default=list)

    # 行为
    max_iterations: Mapped[int] = mapped_column(Integer, default=20)
    tool_timeout: Mapped[int] = mapped_column(Integer, default=120)
    auto_approve_safe: Mapped[bool] = mapped_column(Boolean, default=True)

    # 自定义
    system_prompt_overrides: Mapped[dict] = mapped_column(JSON, default=dict)

    # 元数据
    avatar: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
