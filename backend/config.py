"""应用配置。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从 .env 文件加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API 配置
    api_key: str = ""  # 客户端访问本服务的 API Key
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # LLM 配置
    anthropic_api_key: str = ""
    anthropic_base_url: str | None = None
    model_id: str = "claude-sonnet-4-6-20250514"

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/claude_agent.db"

    # Skills 配置
    skills_dir: str = "./skills"  # 项目级 skills 目录

    # MCP 配置（Claude Code 兼容格式）
    mcp_config_path: str = "./.mcp.json"  # 项目级 MCP Server 配置文件

    # 知识库配置
    kb_storage_path: str = "./data/knowledge_base_files"
    kb_max_file_size_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()
