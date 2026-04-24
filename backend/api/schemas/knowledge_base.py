"""知识库 API Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


# ==================== Knowledge Base ====================


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=200, ge=0, le=2000)


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    chunk_size: int | None = Field(default=None, ge=100, le=10000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)


class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    description: str
    chunk_size: int
    chunk_overlap: int
    document_count: int = 0
    total_chunks: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseList(BaseModel):
    knowledge_bases: list[KnowledgeBaseInfo]
    total: int


# ==================== Document ====================


class UploadUrlRequest(BaseModel):
    url: HttpUrl
    crawl_depth: int = Field(default=0, ge=0, le=3)
    max_pages: int = Field(default=10, ge=1, le=100)


class UploadTextRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    text: str = Field(..., min_length=1)


class DocumentInfo(BaseModel):
    id: str
    knowledge_base_id: str
    title: str
    source_type: str
    source_uri: str
    mime_type: str
    file_size: int
    status: str
    error_message: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DocumentDetail(DocumentInfo):
    raw_text_preview: str = ""


# ==================== Chunk ====================


class ChunkInfo(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    char_count: int
    token_count: int
    section_headers: list[str]
    metadata: dict


class ChunkList(BaseModel):
    chunks: list[ChunkInfo]
    total: int
