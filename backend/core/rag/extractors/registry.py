"""文档提取器注册表。"""

from __future__ import annotations

from pathlib import Path

from backend.core.rag.extractors.base import BaseExtractor
from backend.core.rag.extractors.docx import DocxExtractor
from backend.core.rag.extractors.html import HTMLExtractor
from backend.core.rag.extractors.markdown import MarkdownExtractor
from backend.core.rag.extractors.pdf import PDFExtractor
from backend.core.rag.extractors.plaintext import PlaintextExtractor

# 扩展名 -> MIME 类型映射
EXTENSION_TO_MIME: dict[str, str] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
}

# MIME 类型 -> 提取器映射
_MIME_TO_EXTRACTOR: dict[str, type[BaseExtractor]] = {
    "text/markdown": MarkdownExtractor,
    "application/pdf": PDFExtractor,
    "text/plain": PlaintextExtractor,
    "text/csv": PlaintextExtractor,
    "application/json": PlaintextExtractor,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxExtractor,
    "text/html": HTMLExtractor,
}

# 提取器实例缓存
_extractors: dict[str, BaseExtractor] = {}


def get_mime_type(file_path: Path | str) -> str:
    """根据文件扩展名获取 MIME 类型。"""
    if isinstance(file_path, str):
        file_path = Path(file_path)
    return EXTENSION_TO_MIME.get(file_path.suffix.lower(), "text/plain")


def get_extractor(mime_type: str) -> BaseExtractor:
    """根据 MIME 类型获取提取器实例。"""
    if mime_type not in _extractors:
        extractor_cls = _MIME_TO_EXTRACTOR.get(mime_type, PlaintextExtractor)
        _extractors[mime_type] = extractor_cls()
    return _extractors[mime_type]


def get_extractor_for_file(file_path: Path | str) -> tuple[BaseExtractor, str]:
    """根据文件路径获取提取器和 MIME 类型。"""
    mime_type = get_mime_type(file_path)
    return get_extractor(mime_type), mime_type


def is_supported_extension(ext: str) -> bool:
    """检查文件扩展名是否支持。"""
    return ext.lower() in EXTENSION_TO_MIME
