"""System Prompt Pipeline — Builder 和核心类型。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """每次请求的上下文信息，传递给所有 provider。"""

    channel: str = "web"  # "web" | "wechat" | ...
    session_id: str = ""
    skills: list[Any] = field(default_factory=list)
    mcp_tool_names: set[str] = field(default_factory=set)
    mcp_lazy_mode: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class PromptProvider(ABC):
    """System prompt 片段提供者。

    每个 provider 负责渲染一个 XML 标签包裹的 section。
    """

    section_tag: str = ""

    @abstractmethod
    def render(self, context: PromptContext) -> str:
        """渲染 prompt 片段。返回空字符串则该 section 被跳过。"""


class SystemPromptBuilder:
    """按顺序调用 provider，组装最终 system prompt。"""

    def __init__(self, providers: list[PromptProvider] | None = None):
        self._providers = providers or []

    def add_provider(self, provider: PromptProvider) -> None:
        self._providers.append(provider)

    def build(self, context: PromptContext) -> str:
        """渲染所有 provider，每个非空 section 包裹为 <tag>...\n</tag>。"""
        sections: list[str] = []
        for provider in self._providers:
            try:
                rendered = provider.render(context)
                if rendered and rendered.strip():
                    tag = provider.section_tag
                    sections.append(f"<{tag}>\n{rendered.strip()}\n</{tag}>")
            except Exception:
                logger.exception("PromptProvider %s failed", provider.section_tag)
        return "\n\n".join(sections)
