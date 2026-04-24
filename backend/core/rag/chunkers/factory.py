"""分块器工厂。"""

from backend.core.rag.chunkers.base import BaseChunker
from backend.core.rag.chunkers.markdown_chunker import MarkdownChunker
from backend.core.rag.chunkers.pdf_chunker import PDFChunker
from backend.core.rag.chunkers.recursive_chunker import RecursiveChunker


def get_chunker(
    mime_type: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> BaseChunker:
    """根据 MIME 类型选择合适的分块器。"""
    if mime_type == "text/markdown":
        return MarkdownChunker(chunk_size, chunk_overlap)
    elif mime_type == "application/pdf":
        return PDFChunker(chunk_size, chunk_overlap)
    elif mime_type == "text/html":
        # HTML 提取后已转为 Markdown-like 结构
        return MarkdownChunker(chunk_size, chunk_overlap)
    else:
        return RecursiveChunker(chunk_size, chunk_overlap)
