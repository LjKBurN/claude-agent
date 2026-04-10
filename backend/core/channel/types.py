"""Channel 共享类型定义。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """统一的 Channel 消息格式。"""

    message_id: str
    conversation_id: str  # IM 平台会话 ID（微信: session_id 或 group_id）
    sender_id: str  # 发送者 ID
    text: str  # 消息文本
    raw_data: dict[str, Any] = field(default_factory=dict)  # 原始平台数据
    platform: str = ""  # "wechat" / "feishu"


@dataclass
class ChannelConfig:
    """Channel 配置。"""

    channel_id: str
    platform: str
    name: str
    enabled: bool = True
    allowed_senders: list[str] = field(default_factory=list)
    platform_config: dict[str, Any] = field(default_factory=dict)
