"""Markdown 标题感知分块器。"""

from __future__ import annotations

import re

from backend.core.rag.chunkers.base import BaseChunker
from backend.core.rag.chunkers.recursive_chunker import RecursiveChunker
from backend.core.rag.types import ChunkData

# 匹配 Markdown 标题行
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class MarkdownChunker(BaseChunker):
    """Markdown 结构感知分块器。按标题层级切分，超长章节降级为递归分块。"""

    def chunk(self, text: str, metadata: dict | None = None) -> list[ChunkData]:
        if not text.strip():
            return []

        sections = self._split_by_headers(text)

        # 如果没有找到标题结构，降级为递归分块
        if len(sections) <= 1:
            return RecursiveChunker(self.chunk_size, self.chunk_overlap).chunk(text, metadata)

        # 合并过短的章节，切分过长的章节
        merged = self._merge_short_sections(sections)
        return self._build_chunks(merged)

    def _split_by_headers(self, text: str) -> list[tuple[list[str], str]]:
        """按标题切分为章节。返回 [(section_headers, content), ...]。"""
        lines = text.split("\n")
        sections: list[tuple[list[str], str]] = []
        current_headers: list[str] = []
        current_lines: list[str] = []
        current_level = 0

        for line in lines:
            m = _HEADER_RE.match(line)
            if m:
                # 保存当前章节
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append((list(current_headers), content))

                # 开始新章节
                level = len(m.group(1))
                header_text = m.group(2).strip()

                # 更新标题层级栈
                if level <= current_level:
                    current_headers = current_headers[: level - 1]
                current_headers = current_headers[: level - 1]
                current_headers.append(header_text)
                current_level = level
                current_lines = [line]
            else:
                current_lines.append(line)

        # 最后一个章节
        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append((list(current_headers), content))

        # 如果没有找到标题，把整段文本作为一个章节
        if not sections:
            sections = [([], text)]

        return sections

    def _merge_short_sections(
        self, sections: list[tuple[list[str], str]]
    ) -> list[tuple[list[str], str]]:
        """合并过短的相邻章节。"""
        merged: list[tuple[list[str], str]] = []
        current_headers: list[str] = []
        current_content = ""

        for headers, content in sections:
            candidate = current_content + "\n\n" + content if current_content else content

            if not current_content or len(candidate) <= self.chunk_size * 1.5:
                current_content = candidate
                # 使用第一个非空章节的标题
                if not current_headers and headers:
                    current_headers = headers
            else:
                if current_content:
                    merged.append((current_headers, current_content))
                current_headers = headers
                current_content = content

        if current_content:
            merged.append((current_headers, current_content))

        return merged

    def _build_chunks(self, sections: list[tuple[list[str], str]]) -> list[ChunkData]:
        """将章节转换为 ChunkData，超长章节降级为递归分块。"""
        import tiktoken

        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None

        all_chunks: list[ChunkData] = []
        chunk_index = 0

        for headers, content in sections:
            if len(content) > self.chunk_size * 1.5:
                # 超长章节：递归子分块
                sub_chunker = RecursiveChunker(self.chunk_size, self.chunk_overlap)
                sub_chunks = sub_chunker.chunk(content)
                for sc in sub_chunks:
                    sc.chunk_index = chunk_index
                    sc.section_headers = headers
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
                    )
                )
                chunk_index += 1

        return all_chunks
