"""HTML 文档提取器。"""

from __future__ import annotations

from pathlib import Path

from backend.core.rag.extractors.base import BaseExtractor
from backend.core.rag.types import ExtractedDocument


class HTMLExtractor(BaseExtractor):
    """HTML 文件提取器，使用 BeautifulSoup。"""

    async def extract(self, source: Path | bytes, mime_type: str = "") -> ExtractedDocument:
        from bs4 import BeautifulSoup

        if isinstance(source, bytes):
            html = source.decode("utf-8")
            title = ""
        else:
            html = source.read_text(encoding="utf-8")
            title = source.stem

        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

        # 移除 script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # 保留标题层级结构
        sections = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr"]):
            text = element.get_text(strip=True)
            if not text:
                continue
            if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(element.name[1])
                sections.append(f"{'#' * level} {text}")
            else:
                sections.append(text)

        full_text = "\n\n".join(sections)

        return ExtractedDocument(
            text=full_text,
            title=title or "HTML Document",
            mime_type="text/html",
            metadata={"source_type": "html"},
        )
