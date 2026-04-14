"""Channel Adapter 抽象基类。

每个 IM 平台实现此基类，自行决定消息接收方式（长轮询、WebSocket、Webhook 等）。
"""

from abc import ABC, abstractmethod
from typing import Callable

from backend.core.channel.types import ChannelMessage


class ChannelAdapter(ABC):
    """IM 平台适配器基类。

    子类需实现:
    - start(): 启动消息接收（轮询/WebSocket/Webhook）
    - stop(): 停止消息接收并清理资源
    - send_message(): 发送文本消息
    - send_typing(): 发送正在输入状态
    """

    def __init__(
        self,
        channel_id: str,
        config: dict,
        on_message: Callable,
    ) -> None:
        self.channel_id = channel_id
        self.config = config
        self._on_message = on_message
        self._running = False

    @property
    def is_configured(self) -> bool:
        """是否已配置凭据（如 token）。子类可覆写。"""
        return False

    @property
    def is_running(self) -> bool:
        """是否正在运行（轮询/WebSocket 已启动）。"""
        return self._running

    @abstractmethod
    async def start(self) -> None:
        """启动消息接收。"""

    @abstractmethod
    async def stop(self) -> None:
        """停止消息接收并清理资源。"""

    @abstractmethod
    async def send_message(self, conversation_id: str, text: str, **kwargs) -> None:
        """发送文本消息。"""

    @abstractmethod
    async def send_typing(self, conversation_id: str) -> None:
        """发送正在输入状态。非关键操作，可空实现。"""
