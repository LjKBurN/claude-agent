"""Agent Core — 解耦后的 Agent 核心模块。

提供以下核心抽象：
- LLMProvider: 统一 LLM 调用接口
- AgentLoop: 核心工具调用循环
- EventBus: 事件总线
- ApprovalManager: HITL 审批管理
- SessionManager: 会话管理
- UnifiedToolRegistry: 统一工具注册表
- AgentBuilder: 配置驱动的 Agent 组装
- AgentHook: 生命周期钩子机制
"""

from backend.core.agent.approval import ApprovalManager
from backend.core.agent.builder import AgentBuilder, AgentConfig
from backend.core.agent.events import AgentEvent, EventBus, EventType
from backend.core.agent.hooks import AgentHook, HookContext, KnowledgeRetrievalHook
from backend.core.agent.llm import LLMConfig, LLMProvider, LLMResponse, StreamChunk
from backend.core.agent.loop import AgentLoop, AgentLoopResult, ToolCallRecord
from backend.core.agent.runner import AgentRunner
from backend.core.agent.session import SessionManager
from backend.core.tools.registry import ToolDescriptor, UnifiedToolRegistry

__all__ = [
    # 核心循环
    "AgentLoop",
    "AgentLoopResult",
    "ToolCallRecord",
    # 事件系统
    "EventType",
    "AgentEvent",
    "EventBus",
    # 审批
    "ApprovalManager",
    # 会话
    "SessionManager",
    # 执行器
    "AgentRunner",
    # LLM
    "LLMProvider",
    "LLMConfig",
    "LLMResponse",
    "StreamChunk",
    # 工具
    "UnifiedToolRegistry",
    "ToolDescriptor",
    # 组装
    "AgentBuilder",
    "AgentConfig",
    # Hook
    "AgentHook",
    "HookContext",
    "KnowledgeRetrievalHook",
]
