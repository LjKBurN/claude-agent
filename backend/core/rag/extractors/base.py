"""文档提取器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import tiktoken

from backend.core.rag.types import ExtractedDocument


class BaseExtractor(ABC):
    """文档提取器抽象基类。"""

    @abstractmethod
    async def extract(self, source: Path | bytes, mime_type: str = "") -> ExtractedDocument:
        """从源提取文档内容。"""
        ...

    def _count_tokens(self, text: str) -> int:
        """计算文本的 token 数。"""
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            # fallback: 按字符数估算
            return len(text) // 2
