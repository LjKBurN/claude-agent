"""Skill 注册中心。

管理所有可用的 skills，生成 Skill tool 描述。
"""

from pathlib import Path

from backend.config import get_settings
from backend.core.skills.loader import SkillLoader
from backend.core.skills.types import Skill, SkillResult


class SkillRegistry:
    """Skill 注册中心。"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def load_all(self) -> None:
        """加载所有 skills。"""
        if self._loaded:
            return

        settings = get_settings()

        # 获取项目根目录（backend 的父目录）
        project_root = Path(__file__).parent.parent.parent.parent

        # 定义加载路径（按优先级）
        skill_paths = [
            (project_root / "skills", "project"),  # 项目级 skills
            (Path.home() / ".claude-agent" / "skills", "user"),  # 用户级 skills
            # 内置 skills 可以在这里添加
        ]

        for directory, source in skill_paths:
            if directory.exists():
                skills = SkillLoader.load_skills_from_directory(directory, source)
                for skill in skills:
                    # 后加载的会覆盖先加载的（优先级高的覆盖低的）
                    self._skills[skill.name] = skill

        self._loaded = True

    def reload(self) -> None:
        """重新加载所有 skills。"""
        self._skills.clear()
        self._loaded = False
        self.load_all()

    def get(self, name: str) -> Skill | None:
        """获取指定名称的 skill。"""
        self.load_all()

        # 支持完全限定名（plugin:name 格式）
        if ":" in name:
            _, skill_name = name.split(":", 1)
            return self._skills.get(skill_name)

        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        """列出所有可用的 skills。"""
        self.load_all()
        return list(self._skills.values())

    def list_for_tool(self) -> list[Skill]:
        """列出应该出现在 Skill tool 中的 skills。

        过滤掉：
        - disable_model_invocation=True 的 skills
        - 没有描述的 skills
        """
        self.load_all()

        return [
            skill
            for skill in self._skills.values()
            if not skill.disable_model_invocation and skill.description
        ]

    def get_skill_tool_description(self, max_chars: int = 15000) -> str:
        """生成 Skill tool 的 description 字段。

        这个描述会被注入到 tools 数组中，让 Claude 知道有哪些 skills 可用。

        Args:
            max_chars: 最大字符数限制

        Returns:
            格式化的 Skill tool description
        """
        skills = self.list_for_tool()

        # 分离 mode commands 和 regular skills
        mode_commands = [s for s in skills if s.mode]
        regular_skills = [s for s in skills if not s.mode]

        # 构建可用 skills 列表
        skills_lines = []

        if mode_commands:
            skills_lines.append("## Mode Commands")
            for skill in mode_commands:
                skills_lines.append(skill.get_full_description())
            skills_lines.append("")

        if regular_skills:
            skills_lines.append("## Available Skills")
            for skill in regular_skills:
                skills_lines.append(skill.get_full_description())

        skills_list = "\n".join(skills_lines)

        # 检查字符限制
        if len(skills_list) > max_chars:
            # 截断并添加提示
            skills_list = skills_list[:max_chars] + "\n... (more skills available)"

        return f"""Execute a skill within the main conversation.

<skills_instructions>
When users ask you to perform tasks, check if any of the available skills
below can help complete the task more effectively. Skills provide specialized
capabilities and domain knowledge.

How to use skills:
- Invoke skills using this tool with the skill name only (no arguments)
- When you invoke a skill, you will see a loading message
- The skill's prompt will expand and provide detailed instructions
- Examples:
  - `command: "code_review"` - invoke the code_review skill
  - `command: "doc_gen"` - invoke the doc_gen skill

Important:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands (like /help, /clear, etc.)
</skills_instructions>

<available_skills>
{skills_list}
</available_skills>
"""

    def get_skill_tool_definition(self) -> dict:
        """获取 Skill tool 的完整定义（用于 tools 数组）。"""
        return {
            "name": "Skill",
            "description": self.get_skill_tool_description(),
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The skill name to invoke (no arguments)",
                    }
                },
                "required": ["command"],
            },
        }

    def validate_skill_invocation(self, command: str) -> SkillResult:
        """验证 skill 调用请求。

        Args:
            command: skill 名称

        Returns:
            SkillResult 包含验证结果
        """
        self.load_all()

        # 清理命令名称
        skill_name = command.strip().lstrip("/")

        # 错误 1: 空名称
        if not skill_name:
            return SkillResult(
                success=False,
                command_name="",
                error_message="Empty skill name",
            )

        # 错误 2: 未知的 skill
        skill = self.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                command_name=skill_name,
                error_message=f"Unknown skill: {skill_name}",
            )

        # 错误 3: 禁止模型调用
        if skill.disable_model_invocation:
            error_msg = (
                f"Skill '{skill_name}' can only be "
                f"invoked manually via /{skill_name}"
            )
            return SkillResult(
                success=False,
                command_name=skill_name,
                error_message=error_msg,
            )

        return SkillResult(
            success=True,
            command_name=skill_name,
            skill=skill,
        )

    def format_metadata_message(self, skill: Skill, args: str = "") -> str:
        """生成 skill 加载的元数据消息（用户可见）。"""
        lines = [
            f'<command-message>The "{skill.user_facing_name()}" skill is loading</command-message>',
            f"<command-name>{skill.user_facing_name()}</command-name>",
        ]
        if args:
            lines.append(f"<command-args>{args}</command-args>")

        return "\n".join(lines)

    def format_skill_prompt(self, skill: Skill, context: dict | None = None) -> str:
        """生成完整的 skill prompt（对用户隐藏，发送给 API）。

        包括：
        - {baseDir} 变量替换
        - 资源列表注入
        - 可用工具信息

        Args:
            skill: Skill 对象
            context: 额外的上下文信息

        Returns:
            格式化的 skill prompt
        """
        context = context or {}

        # 获取 base_dir 路径
        base_dir = str(skill.base_dir) if skill.base_dir else ""

        # 进行 {baseDir} 变量替换
        prompt_content = skill.prompt_content
        if base_dir:
            prompt_content = prompt_content.replace("{baseDir}", base_dir)

        # 构建资源信息
        resources_info = self._format_resources_info(skill)

        # 添加可用工具信息
        tools_info = ""
        if skill.allowed_tools:
            tools_str = ", ".join(skill.allowed_tools)
            tools_info = f"\n\n## Available Tools\nYou have access to: {tools_str}"

        # 组合最终 prompt
        parts = [prompt_content]

        if resources_info:
            parts.append(resources_info)

        if tools_info:
            parts.append(tools_info)

        if base_dir:
            parts.append(f"\n\nBase directory: {base_dir}")

        return "".join(parts)

    def _format_resources_info(self, skill: Skill) -> str:
        """生成资源列表信息。"""
        resources = skill.resources
        if not (resources.scripts or resources.references or resources.assets):
            return ""

        lines = ["\n\n## Bundled Resources"]

        # Scripts
        if resources.scripts:
            lines.append("\n### Scripts (executable via Bash)")
            for script in resources.scripts:
                rel_path = script.relative_to(skill.base_dir) if skill.base_dir else script.name
                lines.append(f"- `{rel_path}`")

        # References
        if resources.references:
            lines.append("\n### References (load via Read)")
            for ref in resources.references:
                rel_path = ref.relative_to(skill.base_dir) if skill.base_dir else ref.name
                lines.append(f"- `{rel_path}`")

        # Assets
        if resources.assets:
            lines.append("\n### Assets (reference by path)")
            for asset in resources.assets:
                rel_path = asset.relative_to(skill.base_dir) if skill.base_dir else asset.name
                lines.append(f"- `{rel_path}`")

        return "\n".join(lines)


# 全局注册中心实例
skill_registry = SkillRegistry()
