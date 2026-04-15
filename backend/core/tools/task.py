"""任务管理工具。

提供 create_task / update_task 两个工具，
帮助 Agent 在执行长任务时规划步骤并跟踪进度。
"""

import uuid

from backend.core.tools.base import register_tool

# 内存存储：task_id → task_data
_tasks: dict[str, dict] = {}

# 每个进程最多保留的任务数，防止内存泄漏
_MAX_TASKS = 100


def _format_progress(task: dict) -> str:
    """格式化任务进度。"""
    done = sum(1 for s in task["steps"] if s["done"])
    total = len(task["steps"])
    lines = [f"Task: {task['title']} (id: {task['id']}) — {done}/{total} completed"]
    for i, step in enumerate(task["steps"]):
        mark = "x" if step["done"] else " "
        lines.append(f"  [{mark}] {i}. {step['text']}")
    return "\n".join(lines)


@register_tool(
    name="create_task",
    description=(
        "Create a task plan with a list of steps. "
        "Use this tool when you need to execute a complex multi-step task. "
        "After creating the task, execute each step one by one and call update_task to mark completion."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "A short title describing the overall task.",
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of steps to complete the task.",
            },
        },
        "required": ["title", "steps"],
    },
)
def create_task(arguments: dict) -> str:
    """创建任务计划。"""
    title = arguments["title"]
    steps = arguments["steps"]

    if not steps:
        return "Error: steps cannot be empty"

    # 防止内存泄漏：超过上限时清空旧任务
    if len(_tasks) >= _MAX_TASKS:
        _tasks.clear()

    task_id = uuid.uuid4().hex[:8]
    _tasks[task_id] = {
        "id": task_id,
        "title": title,
        "steps": [{"text": s, "done": False} for s in steps],
    }

    return _format_progress(_tasks[task_id])


@register_tool(
    name="update_task",
    description=(
        "Mark a task step as completed and show current progress. "
        "Call this after finishing each step of a task created with create_task."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID returned by create_task.",
            },
            "step_index": {
                "type": "integer",
                "description": "The index of the step to mark as completed (0-based).",
            },
            "note": {
                "type": "string",
                "description": "Optional note about what was done in this step.",
            },
        },
        "required": ["task_id", "step_index"],
    },
)
def update_task(arguments: dict) -> str:
    """更新任务步骤状态。"""
    task_id = arguments["task_id"]
    step_index = arguments["step_index"]
    note = arguments.get("note", "")

    task = _tasks.get(task_id)
    if not task:
        return f"Error: Task '{task_id}' not found. Create a task first with create_task."

    if step_index < 0 or step_index >= len(task["steps"]):
        return f"Error: Invalid step_index {step_index}. Valid range: 0-{len(task['steps']) - 1}"

    task["steps"][step_index]["done"] = True

    result = _format_progress(task)
    if note:
        result += f"\n  Note: {note}"

    done = sum(1 for s in task["steps"] if s["done"])
    if done == len(task["steps"]):
        result += "\nAll steps completed!"

    return result
