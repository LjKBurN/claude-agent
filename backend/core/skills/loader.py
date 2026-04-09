"""SKILL.md 加载器。

解析 SKILL.md 文件，提取 frontmatter 和 markdown 内容。
扫描 scripts/references/assets 资源目录。
"""

import re
from pathlib import Path

from backend.core.skills.types import Skill, SkillResources


class SkillLoader:
    """加载和解析 SKILL.md 文件。"""

    # SKILL.md 文件名（不区分大小写）
    SKILL_FILE_NAMES = ["SKILL.md", "skill.md", "Skill.md"]

    # 资源目录名
    SCRIPTS_DIR = "scripts"
    REFERENCES_DIR = "references"
    ASSETS_DIR = "assets"

    @classmethod
    def find_skill_files(cls, directory: Path) -> list[Path]:
        """在目录中查找所有 SKILL.md 文件。"""
        skill_files = []

        if not directory.exists():
            return skill_files

        # 检查目录本身是否有 SKILL.md
        for name in cls.SKILL_FILE_NAMES:
            skill_path = directory / name
            if skill_path.exists():
                skill_files.append(skill_path)
                return skill_files  # 根目录只返回一个

        # 检查子目录
        for subdir in directory.iterdir():
            if subdir.is_dir():
                for name in cls.SKILL_FILE_NAMES:
                    skill_path = subdir / name
                    if skill_path.exists():
                        skill_files.append(skill_path)
                        break

        return skill_files

    @classmethod
    def scan_resources(cls, skill_dir: Path) -> SkillResources:
        """扫描 skill 目录下的资源目录。

        Args:
            skill_dir: skill 所在目录

        Returns:
            SkillResources 包含所有资源路径
        """
        resources = SkillResources()

        # 扫描 scripts/
        scripts_dir = skill_dir / cls.SCRIPTS_DIR
        if scripts_dir.exists() and scripts_dir.is_dir():
            resources.scripts = sorted(
                p for p in scripts_dir.rglob("*") if p.is_file()
            )

        # 扫描 references/
        refs_dir = skill_dir / cls.REFERENCES_DIR
        if refs_dir.exists() and refs_dir.is_dir():
            resources.references = sorted(
                p for p in refs_dir.rglob("*") if p.is_file()
            )

        # 扫描 assets/
        assets_dir = skill_dir / cls.ASSETS_DIR
        if assets_dir.exists() and assets_dir.is_dir():
            resources.assets = sorted(
                p for p in assets_dir.rglob("*") if p.is_file()
            )

        return resources

    @classmethod
    def parse_frontmatter(cls, content: str) -> tuple[dict[str, str], str]:
        """解析 markdown 文件的 YAML frontmatter。

        Args:
            content: 文件内容

        Returns:
            (frontmatter_dict, markdown_content)
        """
        # 匹配 --- 包围的 frontmatter
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            # 没有 frontmatter，整个内容作为 markdown
            return {}, content

        frontmatter_str = match.group(1)
        markdown_content = match.group(2)

        # 解析 YAML frontmatter（简单实现，不用 PyYAML）
        frontmatter = {}
        for line in frontmatter_str.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # 处理连字符格式的 key（allowed-tools -> allowed_tools）
                key_normalized = key.replace("-", "_")
                frontmatter[key_normalized] = value

        return frontmatter, markdown_content

    @classmethod
    def load_skill(cls, file_path: Path, source: str = "") -> Skill | None:
        """加载 SKILL.md 文件并返回 Skill 对象。

        Args:
            file_path: SKILL.md 文件路径
            source: 来源标识

        Returns:
            Skill 对象，如果加载失败返回 None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, markdown_content = cls.parse_frontmatter(content)

            # 必需字段检查
            name = frontmatter.get("name", "")
            description = frontmatter.get("description", "")

            if not name:
                # 尝试从目录名获取
                name = file_path.parent.name

            if not description:
                print(f"Warning: Skill '{name}' has no description, will be filtered")
                return None

            # 解析 allowed-tools（逗号分隔的字符串）
            allowed_tools_str = frontmatter.get("allowed_tools", "")
            allowed_tools = [
                t.strip()
                for t in allowed_tools_str.split(",")
                if t.strip()
            ]

            # 解析布尔值
            disable_model_invocation = frontmatter.get(
                "disable_model_invocation", ""
            ).lower() in ("true", "yes", "1")
            mode = frontmatter.get("mode", "").lower() in ("true", "yes", "1")

            # 解析 model
            model = frontmatter.get("model", "")
            if model.lower() == "inherit" or not model:
                model = None

            # 扫描资源目录
            skill_dir = file_path.parent
            resources = cls.scan_resources(skill_dir)

            return Skill(
                name=name,
                description=description,
                prompt_content=markdown_content.strip(),
                allowed_tools=allowed_tools,
                model=model,
                version=frontmatter.get("version", "1.0.0"),
                license=frontmatter.get("license", ""),
                disable_model_invocation=disable_model_invocation,
                mode=mode,
                source=source,
                base_dir=skill_dir,
                resources=resources,
            )

        except Exception as e:
            print(f"Error loading skill from {file_path}: {e}")
            return None

    @classmethod
    def load_skills_from_directory(
        cls, directory: Path, source: str = ""
    ) -> list[Skill]:
        """从目录加载所有 skills。

        Args:
            directory: skills 目录
            source: 来源标识

        Returns:
            加载的 Skill 列表
        """
        skills = []
        skill_files = cls.find_skill_files(directory)

        for file_path in skill_files:
            skill = cls.load_skill(file_path, source)
            if skill:
                skills.append(skill)

        return skills
