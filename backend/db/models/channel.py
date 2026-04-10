"""Channel 数据模型。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Channel(Base):
    """Channel 配置表。"""

    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))  # wechat / feishu
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_senders: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChannelSession(Base):
    """IM 会话 ↔ Agent 会话映射表。"""

    __tablename__ = "channel_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id"))
    im_conversation_id: Mapped[str] = mapped_column(String(200), index=True)
    agent_session_id: Mapped[str] = mapped_column(String(36))
    context_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
