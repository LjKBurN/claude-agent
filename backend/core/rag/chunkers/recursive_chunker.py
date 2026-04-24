"""递归字符分块器 — 支持中文标点的 fallback 分块器。"""

from __future__ import annotations

from backend.core.rag.chunkers.base import BaseChunker
from backend.core.rag.types import ChunkData

# 分隔符优先级：高 → 低，中文标点排在英文前面
SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    ". ",
    "! ",
    "? ",
    "; ",
    "，",
    ", ",
    " ",
    "",
]


class RecursiveChunker(BaseChunker):
    """递归字符文本分块器。按分隔符优先级逐级切分，支持中英文混合文本。"""

    def chunk(self, text: str, metadata: dict | None = None) -> list[ChunkData]:
        if not text.strip():
            return []

        raw_chunks = self._split_text(text)
        return self._build_chunks(raw_chunks)

    def _split_text(self, text: str) -> list[str]:
        """递归切分文本。"""
        return self._recursive_split(text, SEPARATORS)

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if not text:
            return []

        # 文本已经在限制内
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        if not separators:
            # 无分隔符可用，强制按长度切分
            return self._hard_split(text)

        sep = separators[0]
        remaining_seps = separators[1:]

        if sep == "":
            return self._hard_split(text)

        # 按当前分隔符切分
        parts = text.split(sep)
        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                # 当前累积的部分超限
                if current:
                    chunks.append(current)
                # 单个 part 也超限，需要递归用下一级分隔符
                if len(part) > self.chunk_size:
                    sub_chunks = self._recursive_split(part, remaining_seps)
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current)

        return chunks

    def _hard_split(self, text: str) -> list[str]:
        """强制按 chunk_size 切分（带 overlap）。"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - self.chunk_overlap
            if start <= end - self.chunk_size:
                start = end  # 防止无限循环
        return chunks

    def _build_chunks(self, raw_chunks: list[str]) -> list[ChunkData]:
        """将原始文本块转换为 ChunkData。"""
        import tiktoken

        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None

        result = []
        for i, content in enumerate(raw_chunks):
            content = content.strip()
            if not content:
                continue

            token_count = len(enc.encode(content)) if enc else len(content) // 2
            result.append(
                ChunkData(
                    content=content,
                    chunk_index=i,
                    char_count=len(content),
                    token_count=token_count,
                )
            )

        # 重新编号
        for i, chunk in enumerate(result):
            chunk.chunk_index = i

        return result
