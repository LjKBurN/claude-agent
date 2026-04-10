"""Channel 模块。

提供 IM 平台（微信等）与 Agent 之间的消息通道。
"""

from backend.core.channel.types import ChannelConfig, ChannelMessage

__all__ = ["ChannelMessage", "ChannelConfig"]
