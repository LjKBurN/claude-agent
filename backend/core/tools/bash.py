"""Bash 工具 - 执行 Shell 命令。"""

import subprocess

from backend.core.tools.base import register_tool


@register_tool(
    name="bash",
    description="Execute a shell command and return the output.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
        },
        "required": ["command"],
    },
)
def bash(arguments: dict) -> str:
    """Execute a shell command and return the output."""
    command = arguments["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"
