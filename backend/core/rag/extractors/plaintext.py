"""纯文本 / CSV / JSON 提取器。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.rag.extractors.base import BaseExtractor
from backend.core.rag.types import ExtractedDocument


class PlaintextExtractor(BaseExtractor):
    """纯文本文件提取器（txt / csv / json）。"""

    async def extract(self, source: Path | bytes, mime_type: str = "") -> ExtractedDocument:
        if isinstance(source, bytes):
            text = source.decode("utf-8")
            title = ""
        else:
            text = source.read_text(encoding="utf-8")
            title = source.stem

        # JSON 格式化
        if mime_type == "application/json":
            try:
                parsed = json.loads(text)
                text = json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass

        # CSV 转可读文本
        if mime_type == "text/csv":
            text = self._csv_to_text(text)

        return ExtractedDocument(
            text=text,
            title=title or "Text Document",
            mime_type=mime_type or "text/plain",
            metadata={"source_type": "plaintext"},
        )

    @staticmethod
    def _csv_to_text(csv_text: str) -> str:
        """将 CSV 转为可读文本格式。"""
        lines = csv_text.strip().split("\n")
        if len(lines) < 2:
            return csv_text

        headers = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split(",")]
            row_parts = [f"{h}: {v}" for h, v in zip(headers, values)]
            rows.append("; ".join(row_parts))

        return "\n".join(rows)
