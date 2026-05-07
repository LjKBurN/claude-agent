"""AgentBuilder — 配置驱动的 Agent 组装。

Web 端通过 AgentConfig 声明式配置，AgentBuilder 组装出可运行的 AgentLoop。
这是实现"Web 端拼装 Agent"的核心入口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.agent.approval import ApprovalManager
from backend.core.agent.events import EventBus
from backend.core.agent.hooks import KnowledgeRetrievalHook
from backend.core.agent.llm import LLMConfig
from backend.core.agent.llm.anthropic_provider import AnthropicProvider
from backend.core.agent.loop import AgentLoop
from backend.core.tools.registry import UnifiedToolRegistry, populate_registry


@dataclass
class AgentConfig:
    """Agent 的声明性配置。

    可从 JSON 构建，实现 Web UI 驱动的 Agent 创建。
    """

    name: str = "default"
    description: str = ""

    # LLM 配置
    model_id: str = "claude-sonnet-4-6-20250514"
    max_tokens: int = 8000

    # 工具选择
    builtin_tools: list[str] = field(default_factory=list)  # 空 = 全部
    skills: list[str] = field(default_factory=list)          # 空 = 全部 skills
    mcp_servers: list[str] = field(default_factory=list)     # 空 = 全部 MCP servers
    knowledge_base_ids: list[str] = field(default_factory=list)  # 绑定的知识库

    # 行为
    max_iterations: int = 20
    tool_timeout: int = 120
    request_timeout: int = 300
    auto_approve_safe: bool = True

    # 提示词自定义
    system_prompt_overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        """从字典创建配置（Web API 请求体）。"""
        return cls(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            model_id=data.get("model_id", "claude-sonnet-4-6-20250514"),
            max_tokens=data.get("max_tokens", 8000),
            builtin_tools=data.get("builtin_tools", []),
            skills=data.get("skills", []),
            mcp_servers=data.get("mcp_servers", []),
            knowledge_base_ids=data.get("knowledge_base_ids", []),
            max_iterations=data.get("max_iterations", 20),
            tool_timeout=data.get("tool_timeout", 120),
            request_timeout=data.get("request_timeout", 300),
            system_prompt_overrides=data.get("system_prompt_overrides", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（存储/返回给前端）。"""
        return {
            "name": self.name,
            "description": self.description,
            "model_id": self.model_id,
            "max_tokens": self.max_tokens,
            "builtin_tools": self.builtin_tools,
            "skills": self.skills,
            "mcp_servers": self.mcp_servers,
            "knowledge_base_ids": self.knowledge_base_ids,
            "max_iterations": self.max_iterations,
            "tool_timeout": self.tool_timeout,
            "request_timeout": self.request_timeout,
            "system_prompt_overrides": self.system_prompt_overrides,
        }


class AgentBuilder:
    """从 AgentConfig 组装 AgentLoop。

    用法：
        config = AgentConfig(name="code-assistant", builtin_tools=["bash", "read_file"])
        loop = AgentBuilder(config).build()
        result = await loop.run(messages, system_prompt)
    """

    def __init__(self, config: AgentConfig):
        self.config = config

    def build(self, api_key: str = "", base_url: str | None = None) -> AgentLoop:
        """从配置组装 AgentLoop。

        Args:
            api_key: LLM API Key（运行时注入，不存储在配置中）
            base_url: LLM API Base URL（可选）
        """
        # 1. 构建 LLM Provider
        llm = self._build_llm(api_key, base_url)

        # 2. 构建工具注册表
        registry = self._build_registry()

        # 3. 构建审批管理器
        approval = ApprovalManager(registry)

        # 4. 构建事件总线
        event_bus = EventBus()

        # 5. 构建生命周期 hooks
        hooks = self._build_hooks()

        return AgentLoop(
            llm=llm,
            registry=registry,
            events=event_bus,
            approval=approval,
            max_iterations=self.config.max_iterations,
            tool_timeout=self.config.tool_timeout,
            request_timeout=self.config.request_timeout,
            hooks=hooks,
        )

    def _build_llm(self, api_key: str, base_url: str | None) -> Any:
        """根据配置创建 LLM Provider。"""
        config = LLMConfig(
            model_id=self.config.model_id,
            api_key=api_key,
            base_url=base_url,
            max_tokens=self.config.max_tokens,
        )
        return AnthropicProvider(config)

    def _build_registry(self) -> UnifiedToolRegistry:
        """根据配置选择性地构建工具注册表。"""
        builtin_only = self.config.builtin_tools if self.config.builtin_tools else None
        skills = self.config.skills if self.config.skills else None
        mcp_servers = self.config.mcp_servers if self.config.mcp_servers else None

        registry = populate_registry(
            builtin_only=builtin_only,
            skills=skills,
            mcp_servers=mcp_servers,
        )

        return registry

    def _build_hooks(self) -> list:
        """根据配置创建生命周期 hooks。"""
        hooks = []
        if self.config.knowledge_base_ids:
            hooks.append(KnowledgeRetrievalHook(
                knowledge_base_ids=self.config.knowledge_base_ids,
                retrieve_fn=self._make_retrieve_fn(),
            ))
        return hooks

    def _make_retrieve_fn(self):
        """创建知识库检索函数（在组装层解析基础设施依赖）。"""
        async def retrieve(query: str, kb_ids: list[str], top_k: int) -> str:
            from backend.config import get_settings
            settings = get_settings()
            if not settings.zhipu_api_key:
                return ""

            from backend.core.rag.embedding import get_embedding_service
            from backend.core.rag.vector_store import get_vector_store
            from backend.db.database import async_session

            embedding_service = get_embedding_service()
            query_embedding = await embedding_service.embed_query(query)

            vector_store = get_vector_store()
            async with async_session() as db:
                results = await vector_store.search(
                    query_embedding=query_embedding,
                    kb_ids=kb_ids,
                    top_k=top_k,
                    db=db,
                )

            if not results:
                return ""

            parts = []
            for i, r in enumerate(results, 1):
                header = f"[{i}] {r.document_title}"
                if r.section_headers:
                    header += f" > {' > '.join(r.section_headers)}"
                parts.append(f"{header}\n{r.content}")

            return "\n\n---\n\n".join(parts)

        return retrieve
