"""HITL（Human-in-the-Loop）审批管理器。

从 agent_service.py 提取的工具权限检查逻辑。
负责判断工具调用是否需要人工审批。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalManager:
    """管理工具执行的 HITL 审批流程。

    通过 UnifiedToolRegistry（或临时的工具查找回调）检查工具安全性。
    在阶段 3 创建 UnifiedToolRegistry 后，将直接使用 Registry。
    目前保留向后兼容的查找方式。
    """

    def __init__(self, tool_lookup: Any | None = None):
        """
        Args:
            tool_lookup: 工具查找回调或 Registry 实例。
                目前接受一个 callable(name) -> Tool-like object，
                阶段 3 后将接受 UnifiedToolRegistry。
        """
        self._tool_lookup = tool_lookup

    def check(self, content_blocks: list[Any]) -> list[dict]:
        """检查 LLM 响应中的工具调用是否需要审批。

        Args:
            content_blocks: LLM 响应的 content blocks

        Returns:
            需要审批的工具调用列表（空列表 = 全部安全）
        """
        dangerous = []
        for block in content_blocks:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue
            if not self._is_safe(block.name, block.input):
                dangerous.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return dangerous

    def check_serialized(self, content_blocks: list[dict]) -> list[dict]:
        """检查已序列化的 content blocks（dict 形式）。

        用于 HITL 恢复流程中检查 pending_approval 的内容。
        """
        dangerous = []
        for block in content_blocks:
            if block.get("type") != "tool_use":
                continue
            name = block["name"]
            input_data = block["input"]
            if not self._is_safe(name, input_data):
                dangerous.append(block)
        return dangerous

    def _is_safe(self, tool_name: str, tool_input: dict) -> bool:
        """判断单个工具调用是否安全。"""
        if self._tool_lookup is None:
            return True

        # 阶段 3 之前：使用 callable 查找（向后兼容）
        if callable(self._tool_lookup):
            tool = self._tool_lookup(tool_name)
            if tool and hasattr(tool, "is_safe"):
                return tool.is_safe(tool_input)
            # 未注册工具需要审批
            return False

        # 阶段 3 之后：使用 UnifiedToolRegistry
        if hasattr(self._tool_lookup, "is_safe"):
            return self._tool_lookup.is_safe(tool_name, tool_input)

        return False

    @staticmethod
    def is_approval_confirmed(user_message: str) -> bool:
        """检查用户消息是否确认执行。"""
        return "确认" in user_message or "confirm" in user_message.lower()
