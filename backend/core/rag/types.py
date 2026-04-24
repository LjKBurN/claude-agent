"""RAG 核心数据类型。"""

from dataclasses import dataclass, field


@dataclass
class ExtractedDocument:
    """提取后的文档。"""

    text: str
    title: str = ""
    mime_type: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ChunkData:
    """分块数据。"""

    content: str
    chunk_index: int
    char_count: int
    token_count: int = 0
    section_headers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
