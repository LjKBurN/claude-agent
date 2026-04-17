"""Anthropic LLM Provider 实现。

封装 Anthropic SDK 异步调用，包含重试逻辑。
使用 AsyncAnthropic 客户端避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from backend.core.agent.llm.base import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    StreamChunk,
)

logger = logging.getLogger(__name__)

# API 可恢复错误最大重试次数
API_MAX_RETRIES = 3


def _is_retryable_error(exc: Exception) -> bool:
    """判断 API 错误是否可重试。"""
    from anthropic import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        OverloadedError,
        RateLimitError,
        ServiceUnavailableError,
    )

    return isinstance(exc, (
        RateLimitError,
        InternalServerError,
        OverloadedError,
        ServiceUnavailableError,
        APITimeoutError,
        APIConnectionError,
    ))


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 模型的 LLMProvider 实现。

    使用 AsyncAnthropic 异步客户端，所有 API 调用均为非阻塞。
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client_kwargs: dict = {"api_key": config.api_key}
        if config.base_url:
            self._client_kwargs["base_url"] = config.base_url
        self._client = None

    def _get_client(self):
        """延迟创建 AsyncAnthropic 客户端。"""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(**self._client_kwargs)
        return self._client

    async def create(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        """带重试的异步非流式 API 调用。"""
        client = self._get_client()

        for attempt in range(API_MAX_RETRIES):
            try:
                response = await client.messages.create(
                    model=self.config.model_id,
                    max_tokens=self.config.max_tokens,
                    tools=tools or [],
                    messages=messages,
                    system=system or "",
                )
                return LLMResponse(
                    content_blocks=response.content,
                    stop_reason=response.stop_reason,
                    usage={
                        "input_tokens": getattr(response.usage, "input_tokens", 0),
                        "output_tokens": getattr(response.usage, "output_tokens", 0),
                    },
                )
            except Exception as e:
                if not _is_retryable_error(e) or attempt == API_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"API error (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{type(e).__name__}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)

    async def create_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式 API 调用。

        注意：此方法不收集 final_message，无法处理工具调用。
        需要工具调用支持请使用 create_stream_with_result()。
        """
        async for chunk in self.create_stream_with_result(messages, tools, system):
            yield chunk
        return

    async def create_stream_with_result(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """异步流式调用，同时收集工具调用信息。

        使用 AsyncAnthropic 的 async with stream 模式，
        在流结束时额外产出 StreamChunk(type="done")。
        """
        client = self._get_client()

        for attempt in range(API_MAX_RETRIES):
            try:
                async with client.messages.stream(
                    model=self.config.model_id,
                    max_tokens=self.config.stream_max_tokens,
                    tools=tools or [],
                    messages=messages,
                    system=system or "",
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield StreamChunk(type="text", text=event.delta.text)

                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    yield StreamChunk(
                                        type="tool_start",
                                        tool_id=event.content_block.id,
                                        tool_name=event.content_block.name,
                                    )

                    # 保存 final_message
                    self._last_final_message = await stream.get_final_message()

                yield StreamChunk(type="done")
                return

            except Exception as e:
                if not _is_retryable_error(e) or attempt == API_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"API stream error (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{type(e).__name__}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)

    def get_last_final_message(self):
        """获取最近一次流式调用的 final_message。"""
        return getattr(self, "_last_final_message", None)

    def clear_last_final_message(self):
        """清除缓存的 final_message。"""
        self._last_final_message = None

    async def create_simple(
        self,
        messages: list[dict],
        max_tokens: int = 1000,
    ) -> str:
        """简单的异步文本完成（用于摘要生成等，无工具）。"""
        client = self._get_client()

        for attempt in range(API_MAX_RETRIES):
            try:
                response = await client.messages.create(
                    model=self.config.model_id,
                    max_tokens=max_tokens,
                    messages=messages,
                )
                return "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
            except Exception as e:
                if not _is_retryable_error(e) or attempt == API_MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    f"API simple error (attempt {attempt + 1}/{API_MAX_RETRIES}): "
                    f"{type(e).__name__}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)
