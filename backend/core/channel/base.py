"""Channel Adapter 抽象基类。"""

from abc import ABC, abstractmethod
from typing import Callable


class ChannelAdapter(ABC):
    """IM 平台适配器基类。

    每个 IM 平台（微信、飞书等）实现此接口。
    负责与 IM 平台的通信：接收消息、发送消息、管理连接。
    """

    def __init__(self, channel_id: str, config: dict, on_message: Callable):
        """初始化适配器。

        Args:
            channel_id: Channel ID
            config: 平台特定配置
            on_message: 收到消息时的回调函数，签名为 async (channel_id, message) -> None
        """
        self.channel_id = channel_id
        self.config = config
        self._on_message = on_message

    @abstractmethod
    async def start(self) -> None:
        """启动适配器（开始轮询/webhook监听）。"""

    @abstractmethod
    async def stop(self) -> None:
        """停止适配器。"""

    @abstractmethod
    async def send_message(self, conversation_id: str, text: str, **kwargs) -> None:
        """发送消息到 IM 平台。

        Args:
            conversation_id: IM 平台会话 ID
            text: 消息文本
        """

    @abstractmethod
    async def send_typing(self, conversation_id: str) -> None:
        """发送"正在输入"状态。"""
