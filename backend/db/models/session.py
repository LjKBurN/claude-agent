"""会话和消息数据模型。"""

from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Session(Base):
    """会话表。"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关联消息
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    """消息表。"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant / tool / summary
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 上下文压缩相关字段
    is_summarized: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_data: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # 关联会话
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
