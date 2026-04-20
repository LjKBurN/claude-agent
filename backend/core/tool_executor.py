"""工具执行器。

统一处理工具调用，包括普通工具和 Skill meta-tool。
"""

import json
from dataclasses import dataclass

from backend.api.schemas.chat import ToolCall
from backend.core.skills.registry import skill_registry
from backend.core.tools import handle_tool_call


@dataclass
class ToolResult:
    """工具执行结果。"""

    name: str
    output: str
    tool_use_id: str = ""
    messages_to_inject: list[dict] | None = None  # Skill 调用时需要注入的消息


class ToolExecutor:
    """统一处理工具执行，包括 Skill meta-tool。"""

    def execute(
        self,
        tool_name: str,
        tool_input: dict,
        tool_id: str = "",
    ) -> ToolResult:
        """执行工具并返回结果。

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_id: 工具调用 ID（用于构建 tool_result）

        Returns:
            ToolResult 包含执行结果
        """
        if tool_name == "Skill":
            return self._execute_skill(tool_input, tool_id)
        else:
            return self._execute_regular_tool(tool_name, tool_input, tool_id)

    def _execute_regular_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tool_id: str,
    ) -> ToolResult:
        """执行普通工具。"""
        result = handle_tool_call(tool_name, tool_input)
        return ToolResult(
            name=tool_name,
            output=result,
            tool_use_id=tool_id,
        )

    def _execute_skill(self, tool_input: dict, tool_id: str) -> ToolResult:
        """执行 Skill meta-tool。

        返回的 messages_to_inject 需要在调用方注入到消息历史中。
        """
        skill_name = tool_input.get("command", "")

        # 验证 skill 调用
        validation = skill_registry.validate_skill_invocation(skill_name)

        if not validation.success or not validation.skill:
            return ToolResult(
                name="Skill",
                output=json.dumps({
                    "success": False,
                    "error": validation.error_message or f"Unknown skill: {skill_name}",
                }),
                tool_use_id=tool_id,
            )

        skill = validation.skill

        # 构建要注入的消息
        messages_to_inject = []

        # 消息 1: 元数据消息（用户可见）
        metadata_msg = skill_registry.format_metadata_message(skill)
        messages_to_inject.append({
            "role": "user",
            "content": metadata_msg,
        })

        # 消息 2: Skill prompt（对用户隐藏，发送给 API）
        skill_prompt = skill_registry.format_skill_prompt(skill)
        messages_to_inject.append({
            "role": "user",
            "content": skill_prompt,
            "is_meta": True,  # 标记为对用户隐藏
        })

        return ToolResult(
            name="Skill",
            output=json.dumps({
                "success": True,
                "commandName": skill_name,
            }),
            tool_use_id=tool_id,
            messages_to_inject=messages_to_inject,
        )

    def build_tool_result_message(self, results: list[ToolResult]) -> dict:
        """构建 tool_result 消息。"""
        tool_results = []
        for result in results:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": result.tool_use_id,
                "content": result.output,
            })

        return {"role": "user", "content": tool_results}


# 全局实例
tool_executor = ToolExecutor()
