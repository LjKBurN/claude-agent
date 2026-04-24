"""Markdown 文档提取器。"""

from __future__ import annotations

from pathlib import Path

from backend.core.rag.extractors.base import BaseExtractor
from backend.core.rag.types import ExtractedDocument


class MarkdownExtractor(BaseExtractor):
    """Markdown 文件提取器。"""

    async def extract(self, source: Path | bytes, mime_type: str = "") -> ExtractedDocument:
        if isinstance(source, bytes):
            text = source.decode("utf-8")
            title = ""
        else:
            text = source.read_text(encoding="utf-8")
            title = source.stem

        # 从第一行提取标题（# 开头）
        if not title:
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    title = line.lstrip("#").strip()
                    break

        return ExtractedDocument(
            text=text,
            title=title,
            mime_type="text/markdown",
            metadata={"source_type": "markdown"},
        )
