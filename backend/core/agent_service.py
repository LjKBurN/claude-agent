"""Agent 服务封装 — 薄外观，委托给 AgentRunner + SessionManager。"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.agent.builder import AgentBuilder, AgentConfig
from backend.core.agent.llm import LLMConfig, LLMProvider
from backend.core.agent.llm.anthropic_provider import AnthropicProvider
from backend.core.agent.runner import AgentRunner
from backend.core.agent.session import SessionManager
from backend.core.mcp.manager import mcp_manager
from backend.core.prompt import PromptContext, get_system_prompt_builder
from backend.core.skills.registry import skill_registry
from backend.core.tools.registry import UnifiedToolRegistry, populate_registry

logger = logging.getLogger(__name__)

# Agent 执行保护常量（单一来源，与 loop.py 保持一致）
REQUEST_TIMEOUT = 300          # 请求总超时（秒）


class AgentService:
    """Agent 服务 — 薄外观。

    职责仅限于：
    - 公开 API（chat / chat_stream / compress_session 等）
    - MCP 生命周期管理
    - System prompt 构建
    - DB 会话持久化 + SSE 格式化
    - 上下文管理委托

    所有 Agent 执行逻辑委托给 AgentRunner。
    """

    def __init__(self):
        self.settings = get_settings()
        self._mcp_initialized = False
        self._llm: LLMProvider | None = None
        self._registry: UnifiedToolRegistry | None = None
        self._runner: AgentRunner | None = None
        self._session_mgr: SessionManager | None = None

    def _get_llm(self) -> LLMProvider:
        """获取 LLM Provider（延迟创建）。"""
        if self._llm is None:
            config = LLMConfig(
                model_id=self.settings.model_id,
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.anthropic_base_url,
            )
            self._llm = AnthropicProvider(config)
        return self._llm

    def _get_registry(self) -> UnifiedToolRegistry:
        """获取工具注册表（延迟创建，缓存）。"""
        if self._registry is None:
            self._registry = populate_registry()
        return self._registry

    def _refresh_registry(self) -> UnifiedToolRegistry:
        """强制刷新工具注册表（MCP 工具变化后调用）。"""
        self._registry = populate_registry()
        self._runner = None  # runner 缓存失效
        return self._registry

    def _get_session_mgr(self) -> SessionManager:
        """获取会话管理器（延迟创建）。"""
        if self._session_mgr is None:
            self._session_mgr = SessionManager(llm_provider=self._get_llm())
        return self._session_mgr

    def _get_runner(self) -> AgentRunner:
        """获取 AgentRunner（延迟创建，registry 刷新后重建）。"""
        if self._runner is None:
            self._runner = AgentRunner(
                llm=self._get_llm(),
                registry=self._get_registry(),
                request_timeout=REQUEST_TIMEOUT,
            )
        return self._runner

    # ==================== MCP 生命周期 ====================

    async def _ensure_mcp_initialized(self) -> None:
        """确保 MCP 已初始化。"""
        if self._mcp_initialized:
            return

        # 从数据库加载 MCP 配置
        try:
            from backend.db.database import async_session
            async with async_session() as session:
                await mcp_manager.load_configs_from_db(session)
        except Exception as e:
            logger.warning(f"Failed to load MCP configs from DB: {e}")
            # 降级：从 .mcp.json 文件加载
            from pathlib import Path
            project_root = Path(self.settings.mcp_config_path).parent
            mcp_manager.load_all_configs(project_root)

        await mcp_manager.initialize()

        self._mcp_initialized = True
        self._refresh_registry()

    # ==================== System Prompt ====================

    def _get_mcp_tool_names(self) -> set[str]:
        """获取所有 MCP 工具名称集合。"""
        return {t.name for t in self._get_registry().by_source("mcp")}

    def _build_system_prompt(
        self, channel: str = "web", allowed_skills: list[str] | None = None
    ) -> str:
        """构建 system prompt。

        Args:
            channel: 消息渠道
            allowed_skills: 允许的 skill 名称列表。None/空 = 全部 skills。
        """
        builder = get_system_prompt_builder()
        all_skills = skill_registry.list_for_tool()

        if allowed_skills:
            skills = [s for s in all_skills if s.name in allowed_skills]
        else:
            skills = all_skills

        mcp_tool_names = self._get_mcp_tool_names()

        context = PromptContext(
            channel=channel,
            skills=skills,
            mcp_tool_names=mcp_tool_names,
        )
        return builder.build(context)

    # ==================== 公开接口 ====================

    async def chat(
        self,
        user_message: str,
        session_id: str | None,
        db: AsyncSession,
        channel: str = "web",
        agent_config_id: str | None = None,
    ):
        """处理聊天请求（非流式）。"""
        from backend.api.schemas.chat import ToolCall

        await self._ensure_mcp_initialized()
        sm = self._get_session_mgr()

        session = await sm.get_or_create_session(db, session_id)

        if agent_config_id and session_id is None:
            session.agent_config_id = agent_config_id
            await db.flush()

        # HITL 恢复 或 正常流程
        pending_blocks = await sm.check_pending_approval(db, session.id)
        if pending_blocks:
            runner, agent_config = await self._resolve_runner(db, session.agent_config_id)
            messages = await sm.build_resume_messages(
                db, session, user_message, pending_blocks,
                tool_executor_fn=runner.make_tool_executor(),
            )
        else:
            await sm.save_message(db, session.id, "user", user_message)
            messages = await sm.get_messages(db, session.id)
            runner, agent_config = await self._resolve_runner(db, session.agent_config_id)

        allowed_skills = agent_config.skills if agent_config and agent_config.skills else None
        text, tool_call_records, approval_info, content_blocks, orig_count, agent_msgs = (
            await runner.run(messages, self._build_system_prompt(channel, allowed_skills))
        )
        # ToolCallRecord → API 层 ToolCall
        api_tool_calls = [
            ToolCall(name=tc.name, input=tc.input, output=tc.output)
            for tc in tool_call_records
        ]
        return await self._handle_agent_result(
            db, session, text, api_tool_calls, approval_info,
            content_blocks, orig_count, agent_msgs,
        )

    async def chat_stream(
        self,
        user_message: str,
        session_id: str | None,
        db: AsyncSession,
        channel: str = "web",
        agent_config_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """处理聊天请求（流式 SSE）。"""
        await self._ensure_mcp_initialized()
        sm = self._get_session_mgr()

        session = await sm.get_or_create_session(db, session_id)

        if agent_config_id and session_id is None:
            session.agent_config_id = agent_config_id
            await db.flush()

        logger.info(
            f"chat_stream: user_message={user_message!r}, "
            f"session_id={session.id[:8]}, request_sid={session_id[:8] if session_id else None}, "
            f"agent_config_id={session.agent_config_id}"
        )

        pending_blocks = await sm.check_pending_approval(db, session.id)
        if pending_blocks:
            runner, agent_config = await self._resolve_runner(db, session.agent_config_id)
            messages = await sm.build_resume_messages(
                db, session, user_message, pending_blocks,
                tool_executor_fn=runner.make_tool_executor(),
            )
        else:
            await sm.save_message(db, session.id, "user", user_message)
            messages = await sm.get_messages(db, session.id)
            runner, agent_config = await self._resolve_runner(db, session.agent_config_id)

        allowed_skills = agent_config.skills if agent_config and agent_config.skills else None
        async for event in self._stream_agent_response(
            db, session, messages, channel=channel, runner=runner,
            allowed_skills=allowed_skills,
        ):
            yield event

    # ==================== 上下文管理 ====================

    async def compress_session(
        self,
        db: AsyncSession,
        session_id: str,
        keep_recent: int | None = None,
    ) -> dict[str, Any]:
        """主动压缩会话上下文。"""
        sm = self._get_session_mgr()
        sm.set_llm(self._get_llm())
        result = await sm.compress_session(db, session_id, keep_recent)
        sm.invalidate_compress_cache(session_id)
        return result

    async def get_session_stats(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict[str, Any]:
        """获取会话上下文统计信息。"""
        sm = self._get_session_mgr()
        return await sm.get_session_stats(db, session_id)

    async def get_display_messages(
        self,
        db: AsyncSession,
        session_id: str,
        include_summarized: bool = True,
    ) -> list[dict]:
        """获取用于前端展示的消息。"""
        sm = self._get_session_mgr()
        return await sm.get_display_messages(db, session_id, include_summarized)

    # ==================== 内部方法 ====================

    async def _resolve_runner(
        self, db: AsyncSession, agent_config_id: str | None,
    ) -> tuple[AgentRunner, AgentConfig | None]:
        """根据 agent_config_id 解析 AgentRunner。

        - 有 config_id → 从 DB 加载 → AgentBuilder 构建
        - 无 config_id → 使用默认 runner

        Returns:
            (AgentRunner, AgentConfig | None) — config 为 None 表示使用默认配置
        """
        if agent_config_id:
            from sqlalchemy import select as sa_select

            from backend.db.models.agent_config import AgentConfigModel

            result = await db.execute(
                sa_select(AgentConfigModel).where(AgentConfigModel.id == agent_config_id)
            )
            model = result.scalar_one_or_none()
            if model:
                config = AgentConfig(
                    name=model.name,
                    description=model.description,
                    model_id=model.model_id,
                    max_tokens=model.max_tokens,
                    builtin_tools=model.builtin_tools or [],
                    skills=model.skills or [],
                    mcp_servers=model.mcp_servers or [],
                    max_iterations=model.max_iterations,
                    tool_timeout=model.tool_timeout,
                    auto_approve_safe=model.auto_approve_safe,
                    system_prompt_overrides=model.system_prompt_overrides or {},
                )
                agent_loop = AgentBuilder(config).build(
                    api_key=self.settings.anthropic_api_key,
                    base_url=self.settings.anthropic_base_url,
                )
                runner = AgentRunner(
                    llm=agent_loop.llm,
                    registry=agent_loop.registry,
                    max_iterations=config.max_iterations,
                    tool_timeout=config.tool_timeout,
                    request_timeout=config.request_timeout,
                )
                return runner, config
            logger.warning(f"AgentConfig {agent_config_id} not found, falling back to default")

        return self._get_runner(), None

    async def _handle_agent_result(
        self, db, session, response_text, tool_calls, approval_info,
        content_blocks, original_count=None, agent_messages=None,
    ):
        """处理 agent 执行结果（保存消息，返回响应）。"""
        from backend.api.schemas.chat import ChatResponse

        sm = self._get_session_mgr()

        if approval_info:
            if agent_messages and original_count is not None:
                await sm.save_intermediate_messages(
                    db, session.id, agent_messages, original_count
                )
            await sm.save_approval_message(
                db, session.id, response_text, content_blocks,
            )
            await db.commit()
            return ChatResponse(
                session_id=session.id,
                message=response_text,
                tool_calls=tool_calls,
                needs_approval=True,
                approval_info=approval_info,
            )

        await sm.save_message(db, session.id, "assistant", response_text)
        await db.commit()
        return ChatResponse(
            session_id=session.id,
            message=response_text,
            tool_calls=tool_calls,
        )

    async def _stream_agent_response(
        self, db, session, messages, *, channel: str = "web",
        runner: AgentRunner | None = None,
        allowed_skills: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """运行 agent 流式响应并 yield SSE 事件。"""
        from backend.api.schemas.chat import ToolCall

        sm = self._get_session_mgr()
        yield self._sse_event("session_id", {"session_id": session.id})

        full_response = ""
        tool_calls: list[ToolCall] = []

        agent_runner = runner or self._get_runner()
        async for event in agent_runner.run_stream(
            messages, self._build_system_prompt(channel, allowed_skills)
        ):
            if event["type"] == "text":
                full_response += event["content"]
                yield self._sse_event("text", {"content": event["content"]})
            elif event["type"] == "tool_start":
                yield self._sse_event("tool_start", {"name": event["name"]})
            elif event["type"] == "tool_end":
                tc = event["tool_call"]
                api_tc = ToolCall(name=tc.name, input=tc.input, output=tc.output)
                tool_calls.append(api_tc)
                yield self._sse_event("tool_end", {
                    "name": tc.name,
                    "output": tc.output,
                })
            elif event["type"] == "skill_load":
                yield self._sse_event("skill_load", {
                    "name": event["skill_name"],
                    "message": event["message"],
                })
            elif event["type"] == "mcp_tools_loaded":
                yield self._sse_event("mcp_tools_loaded", {
                    "count": event["count"],
                    "tools": event["tools"],
                })
            elif event["type"] == "approval_needed":
                await sm.save_intermediate_messages(
                    db, session.id, event["messages"], event["original_count"]
                )
                await sm.save_approval_message(
                    db, session.id, full_response, event["content_blocks"]
                )
                await db.commit()
                yield self._sse_event("approval_needed", {
                    "message": full_response,
                    "tools": event["tools"],
                })
                yield self._sse_event("done", {"status": "needs_approval"})
                return

        await sm.save_message(db, session.id, "assistant", full_response)
        await db.commit()

        yield self._sse_event("done", {"tool_calls": [
            {"name": tc.name, "input": tc.input, "output": tc.output}
            for tc in tool_calls
        ]})

    def _sse_event(self, event_type: str, data: dict) -> str:
        """生成 SSE 事件字符串。"""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 全局服务实例
agent_service = AgentService()
