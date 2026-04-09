"""Skill 类型定义。

遵循 Claude Code 的 Skill 规范。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillResources:
    """Skill 资源目录。"""

    scripts: list[Path] = field(default_factory=list)  # 可执行脚本
    references: list[Path] = field(default_factory=list)  # 参考文档
    assets: list[Path] = field(default_factory=list)  # 模板和二进制


@dataclass
class Skill:
    """Skill 定义。

    Skill 是基于 Prompt 的元工具，通过注入指令修改对话上下文和执行上下文。
    """

    # 必需字段
    name: str
    description: str
    prompt_content: str

    # 可选配置
    allowed_tools: list[str] = field(default_factory=list)
    model: str | None = None  # None 表示继承当前模型
    version: str = "1.0.0"
    license: str = ""
    disable_model_invocation: bool = False  # True 时只能通过 /skill 手动调用
    mode: bool = False  # True 时作为"模式命令"显示在顶部

    # 元数据
    source: str = ""  # 来源：project, user, builtin, plugin:xxx
    base_dir: Path | None = None  # skill 所在目录
    resources: SkillResources = field(default_factory=SkillResources)  # 资源目录

    def user_facing_name(self) -> str:
        """返回用户可见的名称。"""
        # 如果是 plugin skill，可能包含 plugin 前缀
        if self.source.startswith("plugin:"):
            return f"{self.source[7:]}:{self.name}"
        return self.name

    def get_full_description(self) -> str:
        """返回完整描述（用于 Skill tool 的 available_skills 列表）。"""
        desc = self.description
        if self.source:
            desc = f"{desc} ({self.source})"
        return f'"{self.user_facing_name()}": {desc}'

    def get_tools_description(self) -> str:
        """生成用于注入到 Skill tool description 的文本。"""
        return self.get_full_description()


@dataclass
class SkillContext:
    """Skill 执行上下文。"""

    user_args: str = ""  # 用户传递的参数
    working_directory: str = ""  # 当前工作目录
    session_id: str = ""  # 会话 ID
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 调用结果。"""

    success: bool
    command_name: str
    skill: Skill | None = None
    error_message: str | None = None
