"""核心逻辑模块。

包含 Agent 服务的核心能力：
- AgentService: Agent 服务
- tools: 工具模块
- skills: Skill 系统
"""

# 延迟导入以避免循环依赖
__all__ = [
    "AgentService",
    "agent_service",
]


def __getattr__(name: str):
    """延迟导入。"""
    if name == "AgentService":
        from backend.core.agent_service import AgentService
        return AgentService
    if name == "agent_service":
        from backend.core.agent_service import agent_service
        return agent_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
