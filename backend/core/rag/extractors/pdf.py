"""PDF 文档提取器 — 结构化 Markdown 输出。

使用 PyMuPDF 的 get_text("dict") 提取字体信息用于标题检测，
使用 find_tables() 提取表格结构，输出带语义结构的 Markdown 文本。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.core.rag.extractors.base import BaseExtractor
from backend.core.rag.types import ExtractedDocument

logger = logging.getLogger(__name__)

# bold 标志位 (bit 4)
_BOLD_FLAG = 1 << 4


class PDFExtractor(BaseExtractor):
    """PDF 文件提取器，使用 PyMuPDF 进行结构化提取。"""

    async def extract(self, source: Path | bytes, mime_type: str = "") -> ExtractedDocument:
        return await asyncio.to_thread(self._extract_sync, source)

    def _extract_sync(self, source: Path | bytes) -> ExtractedDocument:
        import fitz

        if isinstance(source, (str, Path)):
            source = Path(source)
            doc = fitz.open(str(source))
            title = source.stem
        else:
            doc = fitz.open(stream=source, filetype="pdf")
            title = ""

        pages = []
        structured = True
        for i, page in enumerate(doc):
            try:
                page_md = self._extract_page_structured(page, i + 1)
            except Exception:
                logger.warning("结构化提取失败，页面 %d 降级为纯文本", i + 1, exc_info=True)
                structured = False
                text = page.get_text()
                page_md = f"--- Page {i + 1} ---\n{text}" if text.strip() else ""
            if page_md.strip():
                pages.append(page_md)

        doc.close()
        full_text = "\n\n".join(pages)

        if not title:
            title = "PDF Document"

        return ExtractedDocument(
            text=full_text,
            title=title,
            mime_type="application/pdf",
            metadata={
                "source_type": "pdf",
                "page_count": len(pages),
                "structured": structured,
            },
        )

    # ------------------------------------------------------------------
    # 结构化提取核心
    # ------------------------------------------------------------------

    def _extract_page_structured(self, page, page_num: int) -> str:
        """处理单页 PDF，返回带结构的 Markdown 文本。"""
        text_dict = page.get_text("dict")

        # 提取表格
        tables = []
        try:
            for table in page.find_tables():
                table_md = self._table_to_markdown(table)
                if table_md:
                    tables.append((table.bbox, table_md))
        except Exception:
            logger.debug("表格检测失败，页面 %d", page_num, exc_info=True)

        # 收集所有可渲染元素: (y_position, element_type, content)
        elements: list[tuple[float, str, str]] = []

        # 表格区域集合（用于跳过表格内的文本块）
        table_rects = [self._normalize_bbox(t[0]) for t in tables]
        for bbox, table_md in tables:
            elements.append((bbox[1], "table", table_md))

        # 分析字体 → 正文基准字号
        all_spans = self._collect_spans(text_dict)
        baseline = self._determine_baseline_size(all_spans)

        # 处理文本块
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            block_bbox = self._normalize_bbox(block["bbox"])
            if self._bbox_overlap_ratio(block_bbox, table_rects) > 0.7:
                continue

            for line in block.get("lines", []):
                line_text, line_size, line_flags = self._merge_line_spans(line.get("spans", []))
                if not line_text.strip():
                    continue

                level = self._classify_heading_level(line_size, baseline, line_flags)
                if level is not None and len(line_text.strip()) >= 3:
                    prefix = "#" * level
                    elements.append((line["bbox"][1], "heading", f"{prefix} {line_text.strip()}"))
                else:
                    elements.append((line["bbox"][1], "text", line_text))

        if not elements:
            return ""

        # 按 y 坐标排序
        elements.sort(key=lambda e: e[0])

        # 组装页面 Markdown
        parts: list[str] = []
        for _, etype, content in elements:
            if etype == "heading":
                parts.append(f"\n{content}\n")
            elif etype == "table":
                parts.append(f"\n{content}\n")
            else:
                parts.append(content)

        page_content = "\n".join(parts).strip()
        return f"--- Page {page_num} ---\n{page_content}" if page_content else ""

    # ------------------------------------------------------------------
    # 字体分析辅助
    # ------------------------------------------------------------------

    def _collect_spans(self, text_dict: dict) -> list[dict]:
        """从 text_dict 中收集所有 span。"""
        spans = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        spans.append(span)
        return spans

    def _determine_baseline_size(self, spans: list[dict]) -> float:
        """确定页面正文字号（按字符数加权众数）。"""
        if not spans:
            return 12.0

        size_chars: dict[float, int] = {}
        for span in spans:
            size = round(span.get("size", 12.0), 1)
            size_chars[size] = size_chars.get(size, 0) + len(span.get("text", ""))

        if not size_chars:
            return 12.0

        return max(size_chars, key=size_chars.get)  # type: ignore[arg-type]

    def _classify_heading_level(self, size: float, baseline: float, flags: int) -> int | None:
        """根据字号和字体标志判断标题层级。

        阈值设计兼顾中英文 PDF 的常见排版：
        - ratio > 1.8 → h1（章节大标题）
        - ratio > 1.4 → h2（节标题）
        - ratio > 1.15 → h3（小节标题）
        - 同字号但加粗且非长段落 → h4（段落级小标题）
        """
        if baseline <= 0:
            return None

        ratio = size / baseline
        is_bold = bool(flags & _BOLD_FLAG)

        if ratio > 1.8:
            return 1
        if ratio > 1.4:
            return 2
        if ratio > 1.15:
            return 3
        # 同字号加粗 → h4（捕获如"猪尊的用途"这类加粗小标题）
        if is_bold and ratio >= 0.95:
            return 4
        return None

    # ------------------------------------------------------------------
    # 文本处理辅助
    # ------------------------------------------------------------------

    def _merge_line_spans(self, spans: list[dict]) -> tuple[str, float, int]:
        """合并同一行的多个 span，返回 (文本, 最大字号, 组合 flags)。"""
        if not spans:
            return "", 0.0, 0

        texts = []
        max_size = 0.0
        combined_flags = 0

        for span in spans:
            text = span.get("text", "")
            texts.append(text)
            size = span.get("size", 0.0)
            if size > max_size:
                max_size = size
            combined_flags |= span.get("flags", 0)

        return "".join(texts), max_size, combined_flags

    # ------------------------------------------------------------------
    # 表格处理
    # ------------------------------------------------------------------

    def _table_to_markdown(self, table) -> str:
        """将 PyMuPDF Table 转换为 Markdown 表格。"""
        try:
            rows = table.extract()
        except Exception:
            return ""

        if not rows or not rows[0]:
            return ""

        col_count = len(rows[0])
        lines: list[str] = []

        for i, row in enumerate(rows):
            # 清理单元格内容
            cells = [str(cell).replace("\n", " ").strip() if cell else "" for cell in row]
            # 补齐列数
            while len(cells) < col_count:
                cells.append("")
            lines.append("| " + " | ".join(cells[:col_count]) + " |")

            # 表头后添加分隔行
            if i == 0:
                lines.append("|" + "|".join(["---"] * col_count) + "|")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 几何辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_bbox(bbox) -> tuple[float, float, float, float]:
        """将 bbox 转为 (x0, y0, x1, y1) 元组。"""
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))

    @staticmethod
    def _bbox_overlap_ratio(bbox: tuple, target_rects: list[tuple]) -> float:
        """计算 bbox 与目标矩形列表的最大面积重叠比。"""
        if not target_rects:
            return 0.0

        x0, y0, x1, y1 = bbox
        area = (x1 - x0) * (y1 - y0)
        if area <= 0:
            return 0.0

        max_ratio = 0.0
        for tx0, ty0, tx1, ty1 in target_rects:
            ox0 = max(x0, tx0)
            oy0 = max(y0, ty0)
            ox1 = min(x1, tx1)
            oy1 = min(y1, ty1)
            if ox1 > ox0 and oy1 > oy0:
                overlap = (ox1 - ox0) * (oy1 - oy0)
                max_ratio = max(max_ratio, overlap / area)

        return max_ratio
