"""搜索工具 — 文件名模式匹配和内容正则搜索。"""

import re
from pathlib import Path

from backend.core.tools.base import register_tool

# 默认忽略的目录
_IGNORE_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode",
    "dist", "build", ".next",
}

# 单个文件最大搜索行数
_MAX_FILE_LINES = 50000


# ============== glob ==============
@register_tool(
    name="glob",
    description=(
        "Find files by name pattern. "
        "Supports glob patterns like '*.py', '**/*.ts', 'src/**/test_*.py'. "
        "Returns matching file paths sorted by modification time."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match file names, e.g. '**/*.py', 'src/**/*.tsx'.",
            },
            "path": {
                "type": "string",
                "description": "Root directory to search in (default: current directory).",
            },
        },
        "required": ["pattern"],
    },
)
def glob_search(arguments: dict) -> str:
    """按文件名模式匹配查找文件。"""
    pattern = arguments["pattern"]
    root = Path(arguments.get("path", "."))

    if not root.exists():
        return f"Error: Directory not found: {root}"
    if not root.is_dir():
        return f"Error: Not a directory: {root}"

    try:
        matches = sorted(
            root.rglob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception as e:
        return f"Error: {str(e)}"

    # 过滤掉忽略目录中的文件
    results = []
    for p in matches:
        if not p.is_file():
            continue
        parts = p.relative_to(root).parts
        if any(part in _IGNORE_DIRS for part in parts):
            continue
        results.append(str(p))
        if len(results) >= 200:
            break

    if not results:
        return f"No files matching '{pattern}' in {root}"

    return "\n".join(results)


# ============== grep ==============
@register_tool(
    name="grep",
    description=(
        "Search file contents by regex pattern. "
        "Returns matching lines with file path and line numbers. "
        "Supports Python regex syntax."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in (default: current directory).",
            },
            "glob": {
                "type": "string",
                "description": "File name filter, e.g. '*.py', '*.ts' (default: all files).",
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines to show around each match (default: 0).",
            },
        },
        "required": ["pattern"],
    },
)
def grep_search(arguments: dict) -> str:
    """按正则表达式搜索文件内容。"""
    pattern = arguments["pattern"]
    root = Path(arguments.get("path", "."))
    glob_filter = arguments.get("glob")
    context_lines = arguments.get("context", 0)

    if not root.exists():
        return f"Error: Path not found: {root}"

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regex: {e}"

    results: list[str] = []
    files_to_search: list[Path]

    if root.is_file():
        files_to_search = [root]
    else:
        glob_pattern = glob_filter or "**/*"
        files_to_search = [
            p for p in root.rglob(glob_pattern)
            if p.is_file()
            and not any(part in _IGNORE_DIRS for part in p.relative_to(root).parts)
        ]

    for filepath in files_to_search:
        if len(results) >= 300:
            break
        try:
            lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
        except (OSError, PermissionError):
            continue

        if len(lines) > _MAX_FILE_LINES:
            continue

        for i, line in enumerate(lines):
            if regex.search(line):
                # 格式: filepath:line_number:content
                results.append(f"{filepath}:{i + 1}:{line.rstrip()}")
                if context_lines > 0:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    for j in range(start, end):
                        if j != i:
                            results.append(f"{filepath}:{j + 1}:{lines[j].rstrip()}")
                if len(results) >= 300:
                    break

    if not results:
        return f"No matches for pattern '{pattern}'"

    # 限制输出长度
    output = "\n".join(results)
    if len(output) > 10000:
        output = output[:10000] + "\n... (truncated)"

    return output
