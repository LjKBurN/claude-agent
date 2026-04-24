"""PDF 结构感知分块器。

先按页码拆分（保留页码追踪），再按 Markdown 标题拆分（复用 MarkdownChunker），
合并短片段后输出带 section_headers + page_numbers 的 ChunkData。
当文档无标题结构时，降级为原有的按页合并策略。
"""

from __future__ import annotations

import re

from backend.core.rag.chunkers.base import BaseChunker
from backend.core.rag.chunkers.markdown_chunker import MarkdownChunker
from backend.core.rag.chunkers.recursive_chunker import RecursiveChunker
from backend.core.rag.types import ChunkData

# 页面分隔标记
_PAGE_BREAK_RE = re.compile(r"^--- Page (\d+) ---$", re.MULTILINE)


class PDFChunker(BaseChunker):
    """PDF 结构感知分块器。先按页切分获取页码，再按标题结构切分，保留页码元数据。"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        super().__init__(chunk_size, chunk_overlap)
        self._md_chunker = MarkdownChunker(chunk_size, chunk_overlap)

    def chunk(self, text: str, metadata: dict | None = None) -> list[ChunkData]:
        if not text.strip():
            return []

        pages = self._split_by_pages(text)
        if not pages:
            return RecursiveChunker(self.chunk_size, self.chunk_overlap).chunk(text, metadata)

        # 对每页内容按 Markdown 标题拆分
        all_sections: list[tuple[list[str], str, list[int]]] = []
        for page_num, page_content in pages:
            sections = self._md_chunker._split_by_headers(page_content)
            for headers, content in sections:
                all_sections.append((headers, content, [page_num]))

        # 如果没有标题结构，降级为按页合并
        if all(len(h) == 0 for h, _, _ in all_sections):
            merged = self._merge_short_pages(pages)
            return self._build_chunks(merged)

        # 合并短章节（保留页码信息）
        merged = self._merge_sections_with_pages(all_sections)
        return self._build_chunks_with_headers(merged)

    # ------------------------------------------------------------------
    # 页码解析（保留原有逻辑）
    # ------------------------------------------------------------------

    def _split_by_pages(self, text: str) -> list[tuple[int, str]]:
        """按页面标记切分。返回 [(page_num, content), ...]。"""
        splits = _PAGE_BREAK_RE.split(text)
        pages: list[tuple[int, str]] = []

        if splits and splits[0].strip():
            pages.append((0, splits[0].strip()))

        for i in range(1, len(splits), 2):
            page_num = int(splits[i])
            content = splits[i + 1].strip() if i + 1 < len(splits) else ""
            if content:
                pages.append((page_num, content))

        return pages

    def _merge_short_pages(self, pages: list[tuple[int, str]]) -> list[tuple[list[int], str]]:
        """合并过短的相邻页面（降级路径）。"""
        merged: list[tuple[list[int], str]] = []
        current_pages: list[int] = []
        current_content = ""

        for page_num, content in pages:
            candidate = current_content + "\n\n" + content if current_content else content

            if not current_content or len(candidate) <= self.chunk_size * 1.5:
                current_content = candidate
                current_pages.append(page_num)
            else:
                if current_content:
                    merged.append((list(current_pages), current_content))
                current_pages = [page_num]
                current_content = content

        if current_content:
            merged.append((list(current_pages), current_content))

        return merged

    # ------------------------------------------------------------------
    # 标题感知分块（新逻辑）
    # ------------------------------------------------------------------

    def _merge_sections_with_pages(
        self, sections: list[tuple[list[str], str, list[int]]]
    ) -> list[tuple[list[str], str, list[int]]]:
        """合并过短的相邻章节，同时追踪页码和继承标题。"""
        merged: list[tuple[list[str], str, list[int]]] = []
        current_headers: list[str] = []
        current_content = ""
        current_pages: list[int] = []
        # 追踪最近出现的标题，用于继承到无标题的延续段落
        last_known_headers: list[str] = []

        for headers, content, page_nums in sections:
            # 记录最近出现的标题
            if headers:
                last_known_headers = headers

            candidate = current_content + "\n\n" + content if current_content else content

            if not current_content or len(candidate) <= self.chunk_size * 1.5:
                current_content = candidate
                if not current_headers and headers:
                    current_headers = headers
                # 合并页码（去重保序）
                for p in page_nums:
                    if p not in current_pages:
                        current_pages.append(p)
            else:
                if current_content:
                    merged.append((current_headers, current_content, current_pages))
                # 无标题的延续段落继承上一个标题
                current_headers = headers if headers else list(last_known_headers)
                current_content = content
                current_pages = list(page_nums)

        if current_content:
            merged.append((current_headers, current_content, current_pages))

        return merged

    def _build_chunks_with_headers(
        self, sections: list[tuple[list[str], str, list[int]]]
    ) -> list[ChunkData]:
        """将章节转换为 ChunkData，超长章节降级为递归分块。"""
        import tiktoken

        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None

        all_chunks: list[ChunkData] = []
        chunk_index = 0

        for headers, content, page_nums in sections:
            if len(content) > self.chunk_size * 1.5:
                sub_chunker = RecursiveChunker(self.chunk_size, self.chunk_overlap)
                sub_chunks = sub_chunker.chunk(content)
                for sc in sub_chunks:
                    sc.chunk_index = chunk_index
                    sc.section_headers = headers
                    sc.metadata["page_numbers"] = page_nums
                    all_chunks.append(sc)
                    chunk_index += 1
            else:
                token_count = len(enc.encode(content)) if enc else len(content) // 2
                all_chunks.append(
                    ChunkData(
                        content=content,
                        chunk_index=chunk_index,
                        char_count=len(content),
                        token_count=token_count,
                        section_headers=headers,
                        metadata={"page_numbers": page_nums},
                    )
                )
                chunk_index += 1

        return all_chunks

    # ------------------------------------------------------------------
    # 降级路径的 chunk 构建（保留原有逻辑）
    # ------------------------------------------------------------------

    def _build_chunks(self, sections: list[tuple[list[int], str]]) -> list[ChunkData]:
        """将按页合并的章节转换为 ChunkData（降级路径）。"""
        import tiktoken

        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None

        all_chunks: list[ChunkData] = []
        chunk_index = 0

        for page_nums, content in sections:
            if len(content) > self.chunk_size * 1.5:
                sub_chunker = RecursiveChunker(self.chunk_size, self.chunk_overlap)
                sub_chunks = sub_chunker.chunk(content)
                for sc in sub_chunks:
                    sc.chunk_index = chunk_index
                    sc.metadata["page_numbers"] = page_nums
                    all_chunks.append(sc)
                    chunk_index += 1
            else:
                token_count = len(enc.encode(content)) if enc else len(content) // 2
                all_chunks.append(
                    ChunkData(
                        content=content,
                        chunk_index=chunk_index,
                        char_count=len(content),
                        token_count=token_count,
                        metadata={"page_numbers": page_nums},
                    )
                )
                chunk_index += 1

        return all_chunks
