"""Channel 共享类型。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """统一消息格式。"""

    message_id: str
    conversation_id: str
    sender_id: str
    text: str
    raw_data: dict[str, Any] = field(default_factory=dict)
    platform: str = ""
