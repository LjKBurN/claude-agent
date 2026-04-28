"""知识库管理 API 路由。"""

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.knowledge_base import (
    ChunkInfo,
    ChunkList,
    CreateKnowledgeBaseRequest,
    DocumentDetail,
    DocumentInfo,
    DocumentList,
    KnowledgeBaseInfo,
    KnowledgeBaseList,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UpdateKnowledgeBaseRequest,
    UploadTextRequest,
    UploadUrlRequest,
)
from backend.config import get_settings
from backend.core.rag.extractors.registry import is_supported_extension
from backend.core.rag.pipeline import DocumentPipeline
from backend.db.database import async_session, get_db
from backend.db.models.knowledge_base import Document, DocumentChunk, KnowledgeBase
from backend.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

_pipeline = DocumentPipeline()


# ==================== Helpers ====================


def _kb_to_info(kb: KnowledgeBase, doc_count: int = 0, chunk_count: int = 0) -> KnowledgeBaseInfo:
    return KnowledgeBaseInfo(
        id=kb.id,
        name=kb.name,
        description=kb.description or "",
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        document_count=doc_count,
        total_chunks=chunk_count,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


def _doc_to_info(doc: Document) -> DocumentInfo:
    return DocumentInfo(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        title=doc.title,
        source_type=doc.source_type,
        source_uri=doc.source_uri or "",
        mime_type=doc.mime_type or "",
        file_size=doc.file_size or 0,
        status=doc.status,
        error_message=doc.error_message or "",
        chunk_count=doc.chunk_count or 0,
        embedding_status=doc.embedding_status or "pending",
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _chunk_to_info(chunk: DocumentChunk) -> ChunkInfo:
    return ChunkInfo(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        char_count=chunk.char_count,
        token_count=chunk.token_count or 0,
        section_headers=chunk.section_headers or [],
        metadata=chunk.metadata_ or {},
    )


async def _get_kb_or_404(kb_id: str, db: AsyncSession) -> KnowledgeBase:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


async def _get_doc_or_404(doc_id: str, db: AsyncSession) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ==================== KB CRUD ====================


@router.get("", response_model=KnowledgeBaseList)
async def list_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> KnowledgeBaseList:
    count_result = await db.execute(select(func.count(KnowledgeBase.id)))
    total = count_result.scalar() or 0

    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
    kbs = result.scalars().all()

    items = []
    for kb in kbs:
        dc = await db.execute(
            select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
        )
        doc_count = dc.scalar() or 0
        cc = await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document)
            .where(Document.knowledge_base_id == kb.id)
        )
        chunk_count = cc.scalar() or 0
        items.append(_kb_to_info(kb, doc_count, chunk_count))

    return KnowledgeBaseList(knowledge_bases=items, total=total)


@router.post("", response_model=KnowledgeBaseInfo, status_code=201)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> KnowledgeBaseInfo:
    existing = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"知识库 '{request.name}' 已存在")

    kb = KnowledgeBase(
        id=str(uuid4()),
        name=request.name,
        description=request.description,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    logger.info("Created knowledge base: %s (%s)", kb.name, kb.id)
    return _kb_to_info(kb)


@router.get("/{kb_id}", response_model=KnowledgeBaseInfo)
async def get_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> KnowledgeBaseInfo:
    kb = await _get_kb_or_404(kb_id, db)
    dc = await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
    )
    doc_count = dc.scalar() or 0
    cc = await db.execute(
        select(func.count(DocumentChunk.id))
        .join(Document)
        .where(Document.knowledge_base_id == kb.id)
    )
    chunk_count = cc.scalar() or 0
    return _kb_to_info(kb, doc_count, chunk_count)


@router.put("/{kb_id}", response_model=KnowledgeBaseInfo)
async def update_knowledge_base(
    kb_id: str,
    request: UpdateKnowledgeBaseRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> KnowledgeBaseInfo:
    kb = await _get_kb_or_404(kb_id, db)

    if request.name is not None and request.name != kb.name:
        existing = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.name == request.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"知识库 '{request.name}' 已存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(kb, key, value)

    await db.commit()
    await db.refresh(kb)
    return _kb_to_info(kb)


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    kb = await _get_kb_or_404(kb_id, db)
    await db.delete(kb)
    await db.commit()

    # 删除存储的文件
    settings = get_settings()
    kb_dir = Path(settings.kb_storage_path) / kb_id
    if kb_dir.exists():
        import shutil

        shutil.rmtree(kb_dir, ignore_errors=True)

    logger.info("Deleted knowledge base: %s (%s)", kb.name, kb.id)
    return {"status": "deleted", "id": kb_id}


# ==================== Document Management ====================


@router.get("/{kb_id}/documents", response_model=DocumentList)
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> DocumentList:
    await _get_kb_or_404(kb_id, db)

    count_result = await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == kb_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    return DocumentList(documents=[_doc_to_info(d) for d in docs], total=total)


@router.post("/{kb_id}/documents/upload", status_code=201)
async def upload_documents(
    kb_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    kb = await _get_kb_or_404(kb_id, db)
    settings = get_settings()
    max_size = settings.kb_max_file_size_mb * 1024 * 1024

    # 确保存储目录存在
    kb_dir = Path(settings.kb_storage_path) / kb_id
    kb_dir.mkdir(parents=True, exist_ok=True)

    created_docs = []
    for file in files:
        # 验证扩展名
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if not is_supported_extension(ext):
            raise HTTPException(
                status_code=400, detail=f"不支持的文件格式: {ext}"
            )

        # 读取文件内容
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件 '{file.filename}' 超过大小限制 ({settings.kb_max_file_size_mb}MB)",
            )

        # 保存文件到磁盘（以 ID 为子目录，保持原始文件名）
        file_id = str(uuid4())
        file_dir = kb_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / (file.filename or "untitled")
        file_path.write_bytes(content)

        # 创建文档记录
        doc = Document(
            id=file_id,
            knowledge_base_id=kb.id,
            title=file.filename or "Untitled",
            source_type="file",
            source_uri=str(file_path),
            mime_type=ext,
            file_size=len(content),
            status="pending",
        )
        db.add(doc)
        created_docs.append(doc)

    await db.commit()
    for doc in created_docs:
        await db.refresh(doc)

    # 触发后台处理
    for doc in created_docs:
        asyncio.create_task(_process_document_bg(doc.id))

    return [_doc_to_info(d) for d in created_docs]


@router.post("/{kb_id}/documents/url", status_code=201)
async def upload_url(
    kb_id: str,
    request: UploadUrlRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    kb = await _get_kb_or_404(kb_id, db)

    doc = Document(
        id=str(uuid4()),
        knowledge_base_id=kb.id,
        title=str(request.url),
        source_type="url",
        source_uri=str(request.url),
        status="pending",
        metadata_={"crawl_depth": request.crawl_depth, "max_pages": request.max_pages},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    asyncio.create_task(
        _process_url_bg(doc.id, str(request.url), request.crawl_depth, request.max_pages)
    )

    return _doc_to_info(doc)


@router.post("/{kb_id}/documents/text", status_code=201)
async def upload_text(
    kb_id: str,
    request: UploadTextRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    kb = await _get_kb_or_404(kb_id, db)

    doc = Document(
        id=str(uuid4()),
        knowledge_base_id=kb.id,
        title=request.title,
        source_type="text",
        source_uri="direct",
        raw_text=request.text,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    asyncio.create_task(_process_document_bg(doc.id))

    return _doc_to_info(doc)


@router.get("/{kb_id}/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> DocumentDetail:
    await _get_kb_or_404(kb_id, db)
    doc = await _get_doc_or_404(doc_id, db)

    if doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail(
        **_doc_to_info(doc).model_dump(),
        raw_text_preview=(doc.raw_text or "")[:500],
    )


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    await _get_kb_or_404(kb_id, db)
    doc = await _get_doc_or_404(doc_id, db)

    if doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # 删除磁盘文件
    if doc.source_type == "file" and doc.source_uri:
        file_path = Path(doc.source_uri)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

    await db.delete(doc)
    await db.commit()

    logger.info("Deleted document: %s (%s)", doc.title, doc.id)
    return {"status": "deleted", "id": doc_id}


@router.post("/{kb_id}/documents/{doc_id}/reprocess", response_model=DocumentInfo)
async def reprocess_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> DocumentInfo:
    await _get_kb_or_404(kb_id, db)
    doc = await _get_doc_or_404(doc_id, db)

    if doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "pending"
    doc.error_message = ""
    doc.embedding_status = "pending"
    await db.commit()

    asyncio.create_task(_process_document_bg(doc.id))
    return _doc_to_info(doc)


# ==================== Chunks ====================


@router.get("/{kb_id}/documents/{doc_id}/chunks", response_model=ChunkList)
async def list_chunks(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ChunkList:
    await _get_kb_or_404(kb_id, db)
    doc = await _get_doc_or_404(doc_id, db)

    if doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    count_result = await db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    return ChunkList(chunks=[_chunk_to_info(c) for c in chunks], total=total)


# ==================== Search ====================


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_bases(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SearchResponse:
    """跨知识库语义搜索。"""
    settings = get_settings()
    if not settings.zhipu_api_key:
        raise HTTPException(status_code=400, detail="未配置 ZHIPU_API_KEY，无法进行语义搜索")

    # 验证知识库存在
    for kb_id in request.knowledge_base_ids:
        await _get_kb_or_404(kb_id, db)

    # 查询向量化
    from backend.core.rag.embedding import get_embedding_service

    embedding_service = get_embedding_service()
    query_embedding = await embedding_service.embed_query(request.query)

    # 向量检索
    from backend.core.rag.vector_store import get_vector_store

    vector_store = get_vector_store()
    results = await vector_store.search(
        query_embedding=query_embedding,
        kb_ids=request.knowledge_base_ids,
        top_k=request.top_k,
        db=db,
    )

    return SearchResponse(
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                content=r.content,
                score=r.score,
                chunk_index=r.chunk_index,
                section_headers=r.section_headers,
            )
            for r in results
        ],
        total=len(results),
    )


# ==================== Background Processing ====================


async def _process_document_bg(doc_id: str) -> None:
    """后台处理文档：提取 → 分块 → 向量化 → 存储。"""
    async with async_session() as db:
        try:
            doc = await _get_doc_or_404(doc_id, db)
            doc.status = "processing"
            await db.commit()

            # 获取知识库配置
            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id)
            )
            kb = kb_result.scalar_one()
            chunk_size = kb.chunk_size
            chunk_overlap = kb.chunk_overlap

            # 处理
            if doc.source_type == "file":
                file_path = Path(doc.source_uri)
                extracted, chunks = await _pipeline.process_file(
                    file_path, chunk_size, chunk_overlap
                )
            elif doc.source_type == "text":
                extracted, chunks = await _pipeline.process_text(
                    doc.raw_text, doc.title, chunk_size, chunk_overlap
                )
            else:
                raise ValueError(f"Unsupported source type: {doc.source_type}")

            # 保存结果
            doc.raw_text = extracted.text
            doc.title = extracted.title or doc.title
            doc.mime_type = extracted.mime_type or doc.mime_type
            doc.chunk_count = len(chunks)
            doc.status = "completed"

            # 删除旧的 chunks
            await db.execute(
                DocumentChunk.__table__.delete().where(
                    DocumentChunk.document_id == doc_id
                )
            )

            # 写入新的 chunks
            chunk_models = []
            for chunk_data in chunks:
                chunk_model = DocumentChunk(
                    id=str(uuid4()),
                    document_id=doc.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    char_count=chunk_data.char_count,
                    token_count=chunk_data.token_count,
                    section_headers=chunk_data.section_headers,
                    metadata_=chunk_data.metadata,
                )
                db.add(chunk_model)
                chunk_models.append(chunk_model)

            await db.flush()  # 确保 chunk_models 有 ID

            # 向量化
            await _embed_chunks(chunk_models, chunks, doc, db)

            await db.commit()
            logger.info("Processed document: %s (%d chunks)", doc.title, len(chunks))

        except Exception as e:
            logger.exception("Failed to process document %s", doc_id)
            try:
                doc = await _get_doc_or_404(doc_id, db)
                doc.status = "failed"
                doc.error_message = str(e)[:1000]
                await db.commit()
            except Exception:
                pass


async def _process_url_bg(
    doc_id: str, url: str, crawl_depth: int, max_pages: int
) -> None:
    """后台处理 URL 爬取。"""
    async with async_session() as db:
        try:
            doc = await _get_doc_or_404(doc_id, db)
            doc.status = "processing"
            await db.commit()

            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id)
            )
            kb = kb_result.scalar_one()

            results = await _pipeline.process_url(
                url, crawl_depth, max_pages, kb.chunk_size, kb.chunk_overlap
            )

            if not results:
                doc.status = "failed"
                doc.error_message = "未获取到任何页面内容"
                await db.commit()
                return

            # 第一个页面更新到主文档
            first_page, first_chunks = results[0]
            doc.raw_text = first_page.text
            doc.title = first_page.title or url
            doc.mime_type = "text/html"
            doc.chunk_count = len(first_chunks)
            doc.status = "completed"

            await db.execute(
                DocumentChunk.__table__.delete().where(
                    DocumentChunk.document_id == doc_id
                )
            )

            first_chunk_models = []
            for chunk_data in first_chunks:
                cm = DocumentChunk(
                    id=str(uuid4()),
                    document_id=doc.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    char_count=chunk_data.char_count,
                    token_count=chunk_data.token_count,
                    section_headers=chunk_data.section_headers,
                    metadata_=chunk_data.metadata,
                )
                db.add(cm)
                first_chunk_models.append(cm)

            await db.flush()
            await _embed_chunks(first_chunk_models, first_chunks, doc, db)

            # 其余页面作为子文档
            for page, page_chunks in results[1:]:
                sub_doc = Document(
                    id=str(uuid4()),
                    knowledge_base_id=kb.id,
                    title=page.title or page.metadata.get("url", "Sub-page"),
                    source_type="url",
                    source_uri=page.metadata.get("url", ""),
                    raw_text=page.text,
                    mime_type="text/html",
                    status="completed",
                    chunk_count=len(page_chunks),
                )
                db.add(sub_doc)
                await db.flush()

                sub_chunk_models = []
                for chunk_data in page_chunks:
                    cm = DocumentChunk(
                        id=str(uuid4()),
                        document_id=sub_doc.id,
                        chunk_index=chunk_data.chunk_index,
                        content=chunk_data.content,
                        char_count=chunk_data.char_count,
                        token_count=chunk_data.token_count,
                        section_headers=chunk_data.section_headers,
                        metadata_=chunk_data.metadata,
                    )
                    db.add(cm)
                    sub_chunk_models.append(cm)

                await db.flush()
                await _embed_chunks(sub_chunk_models, page_chunks, sub_doc, db)

            await db.commit()
            logger.info("Processed URL: %s (%d pages)", url, len(results))

        except Exception as e:
            logger.exception("Failed to process URL %s", url)
            try:
                doc = await _get_doc_or_404(doc_id, db)
                doc.status = "failed"
                doc.error_message = str(e)[:1000]
                await db.commit()
            except Exception:
                pass


# ==================== Embedding Helper ====================


async def _embed_chunks(
    chunk_models: list[DocumentChunk],
    chunk_data_list: list,
    doc: Document,
    db: AsyncSession,
) -> None:
    """对 chunks 进行向量化并更新 embedding 列。失败时不阻塞主流程。"""
    settings = get_settings()
    if not settings.zhipu_api_key:
        doc.embedding_status = "skipped"
        logger.debug("ZHIPU_API_KEY 未配置，跳过向量化")
        return

    doc.embedding_status = "processing"
    await db.flush()

    try:
        from backend.core.rag.embedding import get_embedding_service
        from backend.core.rag.vector_store import get_vector_store

        embedding_service = get_embedding_service()
        vector_store = get_vector_store()

        texts = [c.content for c in chunk_data_list]
        embeddings = await embedding_service.embed_texts(texts)
        chunk_ids = [cm.id for cm in chunk_models]
        await vector_store.store_embeddings(chunk_ids, embeddings, db)

        doc.embedding_status = "completed"
        logger.info("向量化完成: %d chunks", len(chunk_models))
    except Exception:
        doc.embedding_status = "failed"
        logger.warning("向量化失败，chunks 将无向量（仍可用于文本检索）", exc_info=True)
