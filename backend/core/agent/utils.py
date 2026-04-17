"""Agent 核心共享工具函数。"""

from __future__ import annotations

from typing import Any


def extract_text(content_blocks: list[Any]) -> str:
    """从 content blocks 中提取文本（支持 Anthropic SDK 对象和 dict）。"""
    result = []
    for block in content_blocks:
        if isinstance(block, dict):
            if block.get("type") == "text":
                result.append(block.get("text", ""))
        elif hasattr(block, "text"):
            result.append(block.text)
    return "".join(result)


def serialize_blocks(content_blocks: list[Any]) -> list[dict]:
    """将 Anthropic content blocks 序列化为可 JSON 化的 dict 列表。"""
    result = []
    for block in content_blocks:
        if isinstance(block, dict):
            result.append(block)
        elif hasattr(block, "text"):
            result.append({"type": "text", "text": block.text})
        elif hasattr(block, "type") and block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
        elif hasattr(block, "type") and block.type == "tool_result":
            result.append({
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
            })
    return result
