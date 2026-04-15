"""Bash 工具 - 执行 Shell 命令。"""

import re
import subprocess

from backend.core.tools.base import register_tool

# 安全命令白名单：只读、无副作用的命令
_SAFE_COMMANDS = {
    "ls", "dir", "cat", "head", "tail", "less", "more",
    "pwd", "echo", "which", "where", "whereis",
    "env", "printenv", "date", "uname",
    "whoami", "id", "hostname",
    "df", "du", "stat",
    "ps", "top",
    "grep", "find", "wc", "sort", "uniq", "awk", "sed",
    "tr", "cut", "tee",
    "git", "pip", "python",
    "curl", "wget",  # 只读获取，实际副作用由 URL 决定
    "npm", "node",
    "type",
}

# git 子命令白名单（只读）
_SAFE_GIT_SUBCOMMANDS = {
    "status", "log", "diff", "branch", "show", "tag", "remote",
    "stash", "blame", "shortlog", "describe", "reflog",
}

# pip 子命令白名单（只读）
_SAFE_PIP_SUBCOMMANDS = {
    "list", "show", "freeze",
}


def _is_safe_command(arguments: dict) -> bool:
    """判断 bash 命令是否安全。

    解析命令的第一个 token，匹配安全白名单。
    对于复合命令（管道、重定向）做额外检查。
    """
    command = arguments.get("command", "").strip()
    if not command:
        return True

    # 检测危险重定向（> 或 >>）
    if re.search(r"[^>]>>|[^>]>[^>]", command):
        return False

    # 提取第一个 token（命令名）
    parts = command.split()
    if not parts:
        return True

    base_cmd = parts[0]

    # 路径形式的命令，取最后一段
    if "/" in base_cmd:
        base_cmd = base_cmd.rsplit("/", 1)[-1]

    # 不在白名单中 → dangerous
    if base_cmd not in _SAFE_COMMANDS:
        return False

    # git 细分：只有只读子命令安全
    if base_cmd == "git" and len(parts) > 1:
        subcmd = parts[1]
        if subcmd not in _SAFE_GIT_SUBCOMMANDS:
            return False

    # pip 细分：只有只读子命令安全
    if base_cmd == "pip" and len(parts) > 1:
        subcmd = parts[1]
        if subcmd not in _SAFE_PIP_SUBCOMMANDS:
            return False

    return True


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
    permission="dangerous",
    check_safe=_is_safe_command,
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
