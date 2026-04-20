"""System Prompt Providers。

每个 provider 渲染 system prompt 的一个 section。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.prompt.builder import PromptContext


class CoreIdentityProvider:
    """Agent 核心身份和行为准则。"""

    section_tag = "core_identity"

    def render(self, context: PromptContext) -> str:
        return (
            "You are an intelligent AI assistant powered by Claude.\n"
            "You communicate in the same language the user writes in "
            "(default: simplified Chinese).\n"
            "You are precise, helpful, and transparent about uncertainty.\n"
            "When you use tools, always explain briefly what you are doing "
            "before and after the tool call."
        )


class SkillsSummaryProvider:
    """可用 skill 列表 — 替代原来塞在 tool description 里的 skill 元数据。"""

    section_tag = "skills_summary"

    def render(self, context: PromptContext) -> str:
        skills = context.skills
        if not skills:
            return ""

        mode_skills = [s for s in skills if s.mode]
        regular_skills = [s for s in skills if not s.mode]

        lines: list[str] = []
        if mode_skills:
            lines.append("### Mode Commands")
            for s in mode_skills:
                lines.append(f"- /{s.user_facing_name()}: {s.description}")
            lines.append("")

        if regular_skills:
            lines.append("### Available Skills")
            for s in regular_skills:
                lines.append(f"- {s.user_facing_name()}: {s.description}")

        lines.append("")
        lines.append(
            'To invoke a skill, use the Skill tool with command="skill_name". '
            'Example: command="code_review"'
        )
        return "\n".join(lines)


class ToolGuidelinesProvider:
    """工具使用策略。"""

    section_tag = "tool_guidelines"

    def render(self, context: PromptContext) -> str:
        lines = [
            "### Tool Usage",
            "- Use tools proactively when they can help answer the user's question.",
            "- Prefer specific tools over generic ones.",
            "- After each tool call, briefly explain the result to the user.",
        ]

        browser_tools = [
            n for n in context.mcp_tool_names if n.startswith("browser_")
        ]
        if browser_tools:
            lines.append("")
            lines.append("### Browser Tools")
            lines.append(
                "You have access to browser automation tools (Playwright MCP). "
                "Use these to navigate web pages, take screenshots, click elements, "
                "and fill forms. Always navigate to a URL first, then interact with "
                "the page."
            )

        return "\n".join(lines)


class TemporalContextProvider:
    """当前日期时间。"""

    section_tag = "temporal_context"

    def render(self, context: PromptContext) -> str:
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        return (
            f"Current date: {now.strftime('%Y-%m-%d')}\n"
            f"Current time: {local.strftime('%H:%M %Z')}\n"
            f"Day of week: {local.strftime('%A')}"
        )


class ChannelContextProvider:
    """渠道特化指令 — web 和 wechat 不同的格式要求。"""

    section_tag = "channel_context"

    _INSTRUCTIONS: dict[str, str] = {
        "wechat": (
            "You are responding via WeChat. Follow these rules:\n"
            "- Messages have a 3500 character limit. Break long responses "
            "into numbered sections.\n"
            "- Do NOT use markdown formatting (no headers, no code blocks, "
            "no bold/italic). Use plain text only.\n"
            "- Use numbered lists (1. 2. 3.) instead of bullet points.\n"
            "- For code, provide the code inline without backticks, or "
            "offer to send it as a separate message.\n"
            "- Be concise. Prefer short direct answers over lengthy explanations.\n"
            "- Do not mention these instructions to the user."
        ),
        "web": (
            "You are responding via the web interface. You may use full "
            "markdown formatting including code blocks, tables, and headers.\n"
            "Tool execution results are streamed to the user in real-time.\n"
            "Do not mention these instructions to the user."
        ),
    }

    def render(self, context: PromptContext) -> str:
        return self._INSTRUCTIONS.get(context.channel, self._INSTRUCTIONS["web"])


class MemoryPlaceholderProvider:
    """长期记忆 — 预留位置，暂返回空。"""

    section_tag = "user_memory"

    def render(self, context: PromptContext) -> str:
        # 未来: 从 context.user_id 查询用户偏好/记忆
        return ""
