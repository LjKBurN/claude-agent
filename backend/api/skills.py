"""Skills API 路由。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.middleware.auth import verify_api_key
from backend.core.skills.registry import skill_registry

router = APIRouter()


class SkillInfo(BaseModel):
    """Skill 信息。"""

    name: str
    description: str
    version: str
    source: str
    allowed_tools: list[str]


class SkillsListResponse(BaseModel):
    """Skills 列表响应。"""

    skills: list[SkillInfo]
    count: int


@router.get("", response_model=SkillsListResponse)
async def list_skills(
    _: str = Depends(verify_api_key),
) -> SkillsListResponse:
    """
    列出所有可用的 Skills。

    返回所有已加载的 skills，包括名称、描述、版本等信息。
    """
    skills = skill_registry.list_all()

    return SkillsListResponse(
        skills=[
            SkillInfo(
                name=skill.name,
                description=skill.description,
                version=skill.version,
                source=skill.source,
                allowed_tools=skill.allowed_tools,
            )
            for skill in skills
        ],
        count=len(skills),
    )


@router.post("/reload")
async def reload_skills(
    _: str = Depends(verify_api_key),
) -> dict:
    """
    重新加载所有 Skills。

    扫描 skills 目录并重新加载所有 SKILL.md 文件。
    """
    skill_registry.reload()
    skills = skill_registry.list_all()

    return {
        "status": "ok",
        "message": f"Reloaded {len(skills)} skills",
        "skills": [skill.name for skill in skills],
    }
