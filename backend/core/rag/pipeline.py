"""文档处理 Pipeline — 编排提取 → 分块流程。"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.core.rag.chunkers.factory import get_chunker
from backend.core.rag.crawler.web_crawler import WebCrawler
from backend.core.rag.extractors.registry import get_extractor, get_mime_type
from backend.core.rag.types import ChunkData, ExtractedDocument

logger = logging.getLogger(__name__)


class DocumentPipeline:
    """文档处理管线：提取 → 分块。"""

    async def process_file(
        self,
        file_path: Path,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> tuple[ExtractedDocument, list[ChunkData]]:
        """处理文件：提取 → 分块。"""
        mime_type = get_mime_type(file_path)
        extractor = get_extractor(mime_type)
        extracted = await extractor.extract(file_path, mime_type)
        chunks = self._chunk(extracted, chunk_size, chunk_overlap)
        return extracted, chunks

    async def process_bytes(
        self,
        data: bytes,
        filename: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> tuple[ExtractedDocument, list[ChunkData]]:
        """处理字节数据：提取 → 分块。"""
        mime_type = get_mime_type(Path(filename))
        extractor = get_extractor(mime_type)
        extracted = await extractor.extract(data, mime_type)
        if not extracted.title:
            extracted.title = Path(filename).stem
        chunks = self._chunk(extracted, chunk_size, chunk_overlap)
        return extracted, chunks

    async def process_url(
        self,
        url: str,
        crawl_depth: int = 0,
        max_pages: int = 10,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[tuple[ExtractedDocument, list[ChunkData]]]:
        """爬取 URL 并处理每个页面。"""
        crawler = WebCrawler(max_depth=crawl_depth, max_pages=max_pages)
        pages = await crawler.crawl(url)

        results = []
        for page in pages:
            chunks = self._chunk(page, chunk_size, chunk_overlap)
            results.append((page, chunks))

        return results

    async def process_text(
        self,
        text: str,
        title: str = "",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> tuple[ExtractedDocument, list[ChunkData]]:
        """处理直接文本输入。"""
        doc = ExtractedDocument(
            text=text,
            title=title or "Text Input",
            mime_type="text/plain",
            metadata={"source_type": "text"},
        )
        chunks = self._chunk(doc, chunk_size, chunk_overlap)
        return doc, chunks

    def _chunk(
        self,
        doc: ExtractedDocument,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[ChunkData]:
        """根据文档类型选择分块器并执行分块。"""
        chunker = get_chunker(doc.mime_type, chunk_size, chunk_overlap)
        return chunker.chunk(doc.text, doc.metadata)
