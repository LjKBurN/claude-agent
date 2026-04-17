"""LLM Provider 抽象基类和数据类型。

统一不同 LLM 提供商的调用接口，解耦 Agent 核心逻辑对 Anthropic SDK 的直接依赖。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMConfig:
    """LLM 连接配置。"""

    model_id: str = "claude-sonnet-4-6-20250514"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 8000
    stream_max_tokens: int = 4096


@dataclass
class LLMResponse:
    """LLM 非流式响应的统一表示。"""

    content_blocks: list[Any] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens"
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """提取所有文本内容块。"""
        return "".join(
            b.text for b in self.content_blocks if hasattr(b, "text")
        )

    def tool_use_blocks(self) -> list[dict]:
        """提取所有工具使用块为字典形式。"""
        return [
            {"id": b.id, "name": b.name, "input": b.input}
            for b in self.content_blocks
            if hasattr(b, "type") and b.type == "tool_use"
        ]

    def has_tool_calls(self) -> bool:
        """是否有工具调用。"""
        return self.stop_reason == "tool_use"


@dataclass
class StreamChunk:
    """流式输出的单个块。"""

    type: str  # "text" | "tool_start" | "done"
    text: str = ""
    tool_id: str = ""
    tool_name: str = ""


class LLMProvider(ABC):
    """LLM 服务提供商的抽象基类。"""

    @abstractmethod
    async def create(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        """非流式完成。"""

    @abstractmethod
    async def create_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式完成，以 StreamChunk 形式产出。"""

    @abstractmethod
    async def create_simple(
        self,
        messages: list[dict],
        max_tokens: int = 1000,
    ) -> str:
        """简单的文本完成（用于摘要生成等，无工具调用）。"""
