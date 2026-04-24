"""PDF 结构化提取与分块验证测试。"""

import pytest


def _create_test_pdf() -> bytes:
    """创建一个包含标题、副标题、正文和表格的测试 PDF。"""
    import fitz

    doc = fitz.open()

    # --- 第一页 ---
    page1 = doc.new_page(width=612, height=792)

    # 大标题 (h1)
    page1.insert_text((72, 72), "项目概述", fontsize=24, fontname="helv")
    # 副标题 (h2)
    page1.insert_text((72, 120), "1.1 项目背景", fontsize=16, fontname="helv")
    # 正文
    page1.insert_text((72, 160), "本项目是一个企业级 AI Agent 服务。", fontsize=12, fontname="helv")
    page1.insert_text(
        (72, 180),
        "系统采用 FastAPI 框架，支持多轮对话和工具调用。",
        fontsize=12,
        fontname="helv",
    )

    # 手动绘制一个简单表格
    table_data = [
        ["模块", "技术栈", "版本"],
        ["后端", "FastAPI", "0.104"],
        ["前端", "Next.js", "14.0"],
        ["数据库", "SQLite", "3.0"],
    ]
    # 使用 insert_text 模拟表格内容
    y_start = 220
    for i, row in enumerate(table_data):
        y = y_start + i * 20
        page1.insert_text((72, y), "  |  ".join(row), fontsize=12, fontname="helv")
        # 画横线
        page1.draw_line(fitz.Point(72, y + 4), fitz.Point(500, y + 4))

    # 另一个副标题 (h2)
    page1.insert_text((72, 320), "1.2 项目目标", fontsize=16, fontname="helv")
    page1.insert_text((72, 360), "构建可扩展的 AI Agent 平台。", fontsize=12, fontname="helv")
    page1.insert_text((72, 380), "支持知识库检索增强生成（RAG）。", fontsize=12, fontname="helv")

    # --- 第二页 ---
    page2 = doc.new_page(width=612, height=792)

    # 新章节 (h1)
    page2.insert_text((72, 72), "技术架构", fontsize=24, fontname="helv")
    # 副标题 (h3) - 小一点的标题
    page2.insert_text((72, 120), "2.1.1 核心组件", fontsize=14, fontname="helv")
    page2.insert_text((72, 160), "系统由 API 网关、Agent 核心和工具系统组成。", fontsize=12, fontname="helv")
    page2.insert_text(
        (72, 180), "Agent 核心使用 LangGraph 进行状态管理和流程编排。", fontsize=12, fontname="helv"
    )

    data = doc.tobytes()
    doc.close()
    return data


class TestPDFExtractor:
    """测试 PDF 结构化提取。"""

    def test_structured_extraction_produces_headings(self):
        """验证提取结果包含 Markdown 标题。"""
        from backend.core.rag.extractors.pdf import PDFExtractor

        extractor = PDFExtractor()
        pdf_bytes = _create_test_pdf()

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(extractor.extract(pdf_bytes))

        # 应包含页码标记
        assert "--- Page 1 ---" in result.text
        assert "--- Page 2 ---" in result.text

        # 应包含标题（字体较大的文本被识别为标题）
        assert "#" in result.text

        # metadata 应标记为结构化
        assert result.metadata["structured"] is True
        assert result.metadata["page_count"] == 2

    def test_fallback_on_error(self):
        """验证异常时降级为纯文本提取。"""
        from unittest.mock import patch

        from backend.core.rag.extractors.pdf import PDFExtractor

        extractor = PDFExtractor()
        pdf_bytes = _create_test_pdf()

        # 让 _extract_page_structured 抛出异常
        with patch.object(extractor, "_extract_page_structured", side_effect=RuntimeError("test")):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(extractor.extract(pdf_bytes))

            # 应降级为纯文本，仍有内容
            assert result.text.strip() != ""
            assert result.metadata["structured"] is False

    def test_baseline_size_detection(self):
        """验证正文字号检测。"""
        from backend.core.rag.extractors.pdf import PDFExtractor

        extractor = PDFExtractor()

        # 模拟 spans：12pt 占多数（正文），24pt 和 16pt 是标题
        spans = [
            {"text": "正文内容一段", "size": 12.0},
            {"text": "正文内容二段", "size": 12.0},
            {"text": "正文内容三段比较长", "size": 12.0},
            {"text": "大标题", "size": 24.0},
            {"text": "副标题", "size": 16.0},
        ]

        baseline = extractor._determine_baseline_size(spans)
        assert baseline == 12.0

    def test_heading_classification(self):
        """验证标题等级分类。"""
        from backend.core.rag.extractors.pdf import PDFExtractor

        extractor = PDFExtractor()
        baseline = 12.0

        # ratio > 1.8 → h1
        assert extractor._classify_heading_level(24.0, baseline, 0) == 1
        # ratio > 1.4 → h2
        assert extractor._classify_heading_level(18.0, baseline, 0) == 2
        # ratio > 1.15 → h3
        assert extractor._classify_heading_level(14.5, baseline, 0) == 3
        # 同字号加粗 → h4
        assert extractor._classify_heading_level(12.0, baseline, 1 << 4) == 4
        # 正文（同字号不加粗）
        assert extractor._classify_heading_level(12.0, baseline, 0) is None
        # 正文（略大但不够且不加粗）
        assert extractor._classify_heading_level(13.0, baseline, 0) is None

    def test_table_to_markdown(self):
        """验证表格转 Markdown。"""
        from backend.core.rag.extractors.pdf import PDFExtractor

        extractor = PDFExtractor()

        class MockTable:
            def extract(self):
                return [
                    ["模块", "技术栈"],
                    ["后端", "FastAPI"],
                    ["前端", "Next.js"],
                ]

        md = extractor._table_to_markdown(MockTable())
        assert "| 模块 | 技术栈 |" in md
        assert "|---|---|" in md
        assert "| 后端 | FastAPI |" in md


class TestPDFChunker:
    """测试 PDF 结构感知分块。"""

    def test_chunk_with_headers(self):
        """验证带标题结构的 PDF 分块结果。"""
        from backend.core.rag.chunkers.pdf_chunker import PDFChunker

        text = (
            "--- Page 1 ---\n"
            "# 项目概述\n"
            "这是项目概述的内容。\n\n"
            "## 项目背景\n"
            "背景描述文字。\n\n"
            "--- Page 2 ---\n"
            "# 技术架构\n"
            "架构说明内容。\n\n"
            "### 核心组件\n"
            "组件描述文字。\n"
        )

        chunker = PDFChunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk(text)

        assert len(chunks) > 0

        # 每个 chunk 应有 section_headers
        for chunk in chunks:
            assert isinstance(chunk.section_headers, list)
            assert "page_numbers" in chunk.metadata

        # 验证标题传播
        header_chunks = [c for c in chunks if c.section_headers]
        assert len(header_chunks) > 0

    def test_chunk_fallback_no_headers(self):
        """验证无标题时降级为按页合并。"""
        from backend.core.rag.chunkers.pdf_chunker import PDFChunker

        text = (
            "--- Page 1 ---\n"
            "这是一段纯文本内容，没有任何标题结构。\n"
            "只有普通的段落文字。\n\n"
            "--- Page 2 ---\n"
            "第二页也是纯文本。\n"
        )

        chunker = PDFChunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        # 降级路径：无 section_headers，但有 page_numbers
        for chunk in chunks:
            assert "page_numbers" in chunk.metadata

    def test_chunk_empty_text(self):
        """验证空文本返回空列表。"""
        from backend.core.rag.chunkers.pdf_chunker import PDFChunker

        chunker = PDFChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_page_tracking_across_sections(self):
        """验证跨页章节的页码追踪。"""
        from backend.core.rag.chunkers.pdf_chunker import PDFChunker

        text = (
            "--- Page 1 ---\n"
            "# 长章节\n"
            "第一页的内容。\n\n"
            "--- Page 2 ---\n"
            "同一章节在第二页的延续。\n"
        )

        chunker = PDFChunker(chunk_size=1000, chunk_overlap=50)
        chunks = chunker.chunk(text)

        # 短内容应合并为一个 chunk
        assert len(chunks) == 1
        # 应包含两个页码
        assert 1 in chunks[0].metadata["page_numbers"]
        assert 2 in chunks[0].metadata["page_numbers"]
        # 标题应被保留
        assert "长章节" in chunks[0].section_headers


class TestPDFPipeline:
    """端到端测试：提取 → 分块。"""

    def test_full_pipeline(self):
        """验证从 PDF 字节到最终 chunks 的完整流程。"""
        from backend.core.rag.extractors.pdf import PDFExtractor
        from backend.core.rag.chunkers.pdf_chunker import PDFChunker

        import asyncio

        pdf_bytes = _create_test_pdf()

        # 提取
        extractor = PDFExtractor()
        extracted = asyncio.get_event_loop().run_until_complete(extractor.extract(pdf_bytes))

        assert extracted.text.strip() != ""
        assert extracted.metadata["page_count"] == 2

        # 分块
        chunker = PDFChunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk(extracted.text)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content.strip() != ""
            assert chunk.char_count > 0
            assert chunk.token_count > 0
            assert "page_numbers" in chunk.metadata
