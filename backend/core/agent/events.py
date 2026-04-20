"""Agent 事件系统。

定义事件类型和 EventBus，用于 Agent 组件间的解耦通信。
Agent 核心循环通过 EventBus 发出事件，消费者（SSE、WebSocket、日志等）订阅处理。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Agent 事件类型。"""

    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    SKILL_LOAD = "skill_load"
    APPROVAL_NEEDED = "approval_needed"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Agent 循环发出的结构化事件。"""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """进程内事件总线。

    Agent 核心循环通过 emit() 发出事件，多个消费者可以通过以下方式订阅：
    1. subscribe_queue() — 获取 asyncio.Queue，适合异步消费（如 SSE 推送）
    2. subscribe(handler) — 注册回调函数，适合同步处理（如日志）

    Args:
        queue_maxsize: 订阅队列最大容量。0 = 无界（默认），>0 时超出丢弃旧事件。
    """

    def __init__(self, queue_maxsize: int = 0):
        self._queues: list[asyncio.Queue[AgentEvent]] = []
        self._handlers: list[Callable[[AgentEvent], Any]] = []
        self._queue_maxsize = queue_maxsize

    def subscribe_queue(self) -> asyncio.Queue[AgentEvent]:
        """创建一个队列供消费者异步读取。"""
        q: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._queues.append(q)
        return q

    def unsubscribe_queue(self, q: asyncio.Queue[AgentEvent]) -> None:
        """移除订阅的队列，防止内存泄漏。"""
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def subscribe(self, handler: Callable[[AgentEvent], Any]) -> None:
        """注册一个回调处理函数。"""
        self._handlers.append(handler)

    async def emit(self, event: AgentEvent) -> None:
        """向所有订阅者广播一个事件。

        队列满时使用非阻塞写入并丢弃事件，避免慢消费者阻塞 Agent 循环。
        """
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus queue full (size=%d), dropping event: %s",
                    self._queue_maxsize, event.type,
                )
        for handler in self._handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

    @staticmethod
    def to_sse(event: AgentEvent) -> str:
        """将事件转换为 SSE 线格式字符串。"""
        return f"event: {event.type.value}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
