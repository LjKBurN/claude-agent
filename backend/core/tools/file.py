"""文件操作工具 - 读写、编辑、列出目录。"""

from pathlib import Path

from backend.core.tools.base import register_tool


# ============== read_file ==============
@register_tool(
    name="read_file",
    description="Read a file and return its contents.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to read",
            },
        },
        "required": ["file_path"],
    },
)
def read_file(arguments: dict) -> str:
    """Read a file and return its contents."""
    file_path = arguments["file_path"]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============== write_file ==============
@register_tool(
    name="write_file",
    description="Write content to a file. Creates if doesn't exist, overwrites if it does.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    },
    permission="dangerous",
)
def write_file(arguments: dict) -> str:
    """Write content to a file. Creates if doesn't exist, overwrites if it does."""
    file_path = arguments["file_path"]
    content = arguments["content"]
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============== edit_file ==============
@register_tool(
    name="edit_file",
    description="Replace old_string with new_string in a file. Must read file first.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to replace (must exist in the file)",
            },
            "new_string": {
                "type": "string",
                "description": "The new string to replace the old string with",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    },
    permission="dangerous",
)
def edit_file(arguments: dict) -> str:
    """Replace old_string with new_string in a file. Must read file first."""
    file_path = arguments["file_path"]
    old_string = arguments["old_string"]
    new_string = arguments["new_string"]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: old_string not found in file: {file_path}"

        count = content.count(old_string)
        if count > 1:
            return f"Error: old_string appears {count} times in file, must be unique"

        new_content = content.replace(old_string, new_string)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited {file_path}"
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============== list_dir ==============
@register_tool(
    name="list_dir",
    description="List files and directories in a directory.",
    input_schema={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "The directory path to list (default: current directory)",
            },
        },
        "required": [],
    },
)
def list_dir(arguments: dict) -> str:
    """List files and directories in a directory."""
    directory = arguments.get("directory", ".")
    try:
        path = Path(directory)
        if not path.exists():
            return f"Error: Directory not found: {directory}"
        if not path.is_dir():
            return f"Error: Not a directory: {directory}"

        items = []
        for item in sorted(path.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            items.append(f"[{item_type}] {item.name}")

        return "\n".join(items) if items else "(empty directory)"
    except Exception as e:
        return f"Error: {str(e)}"
