"""文档分块器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.core.rag.types import ChunkData


class BaseChunker(ABC):
    """文档分块器抽象基类。"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk(self, text: str, metadata: dict | None = None) -> list[ChunkData]:
        """将文本分块。"""
        ...
