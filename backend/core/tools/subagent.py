"""子 Agent 委托工具 — 将自包含子任务隔离到独立上下文空间执行。

核心价值：上下文隔离。子 Agent 的探索过程（读文件、搜索、试错）不污染
父 Agent 的上下文窗口，父 Agent 只接收最终结果文本。

递归防护：子 Agent 使用 SUB_AGENT_TOOLS 白名单构建 registry，
不包含 spawn_subagent / create_task / update_task，
LLM 无法调用一个不存在的工具 → 物理层面阻断递归。
"""

from backend.core.tools.base import register_tool

# 子 Agent 可用的工具白名单。
# 不含 spawn_subagent（防递归）、create_task / update_task（隔离任务管理）。
SUB_AGENT_TOOLS: list[str] = [
    "bash",
    "read_file",
    "write_file",
    "edit_file",
    "list_dir",
    "glob",
    "grep",
    "http_request",
]

SUB_AGENT_SYSTEM_PROMPT = (
    "你是一个子任务执行者。你会收到一个明确的任务，请高效完成并返回结果。\n"
    "规则：\n"
    "- 直接执行任务，返回完整的结果\n"
    "- 如果任务无法完成，说明原因\n"
    "- 使用提供的工具获取必要信息\n"
    "- 不要解释你的思路，只返回结果"
)


@register_tool(
    name="spawn_subagent",
    description=(
        "Spawn an independent sub-agent to execute a self-contained task "
        "in an isolated context. The sub-agent has access to basic tools "
        "(file read/write, search, bash, http) but cannot spawn further "
        "sub-agents. Use this for tasks where the exploration process "
        "(reading files, searching, trial-and-error) would consume too much "
        "context in the main conversation. The sub-agent returns only the "
        "final result, keeping the main context clean.\n\n"
        "Good use cases:\n"
        "- Analyze a directory structure and extract specific information\n"
        "- Search for patterns across multiple files\n"
        "- Perform independent research that doesn't need main conversation context"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "The specific task for the sub-agent to execute. "
                    "Should be self-contained and clear enough to complete "
                    "independently."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional background information from the parent agent "
                    "to help the sub-agent understand the task better."
                ),
            },
        },
        "required": ["task"],
    },
)
def spawn_subagent(arguments: dict) -> str:
    """占位 handler — 实际执行在 AgentLoop._execute_sub_agent 中。"""
    return "[sub-agent execution handled by AgentLoop]"
