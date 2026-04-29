"""System Prompt Pipeline。"""

from backend.core.prompt.builder import PromptContext, PromptProvider, SystemPromptBuilder
from backend.core.prompt.providers import (
    ChannelContextProvider,
    CoreIdentityProvider,
    KnowledgeContextProvider,
    MemoryPlaceholderProvider,
    SkillsSummaryProvider,
    TemporalContextProvider,
    ToolGuidelinesProvider,
)

# 按顺序组装 builder（单例）
_system_prompt_builder = SystemPromptBuilder(providers=[
    CoreIdentityProvider(),
    KnowledgeContextProvider(),
    SkillsSummaryProvider(),
    ToolGuidelinesProvider(),
    TemporalContextProvider(),
    ChannelContextProvider(),
    MemoryPlaceholderProvider(),
])


def get_system_prompt_builder() -> SystemPromptBuilder:
    return _system_prompt_builder


__all__ = [
    "PromptContext",
    "PromptProvider",
    "SystemPromptBuilder",
    "get_system_prompt_builder",
]
