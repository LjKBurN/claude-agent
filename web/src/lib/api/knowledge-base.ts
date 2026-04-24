import { request, uploadFiles } from "./client";
import type {
  KnowledgeBaseInfo,
  KnowledgeBaseList,
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
  DocumentList,
  DocumentDetail,
  DocumentInfo,
  ChunkList,
} from "./types";

// ==================== Knowledge Base ====================

export function listKnowledgeBases(signal?: AbortSignal) {
  return request<KnowledgeBaseList>(
    "GET",
    "/api/knowledge-bases",
    undefined,
    signal
  );
}

export function getKnowledgeBase(id: string, signal?: AbortSignal) {
  return request<KnowledgeBaseInfo>(
    "GET",
    `/api/knowledge-bases/${id}`,
    undefined,
    signal
  );
}

export function createKnowledgeBase(data: CreateKnowledgeBaseRequest) {
  return request<KnowledgeBaseInfo>("POST", "/api/knowledge-bases", data);
}

export function updateKnowledgeBase(
  id: string,
  data: UpdateKnowledgeBaseRequest
) {
  return request<KnowledgeBaseInfo>(
    "PUT",
    `/api/knowledge-bases/${id}`,
    data
  );
}

export function deleteKnowledgeBase(id: string) {
  return request<{ status: string; id: string }>(
    "DELETE",
    `/api/knowledge-bases/${id}`
  );
}

// ==================== Documents ====================

export function listDocuments(kbId: string, signal?: AbortSignal) {
  return request<DocumentList>(
    "GET",
    `/api/knowledge-bases/${kbId}/documents`,
    undefined,
    signal
  );
}

export function uploadDocuments(kbId: string, files: File[]) {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  return uploadFiles<DocumentInfo[]>(
    `/api/knowledge-bases/${kbId}/documents/upload`,
    formData
  );
}

export function uploadUrl(
  kbId: string,
  url: string,
  crawlDepth: number = 0,
  maxPages: number = 10
) {
  return request<DocumentInfo>(
    "POST",
    `/api/knowledge-bases/${kbId}/documents/url`,
    { url, crawl_depth: crawlDepth, max_pages: maxPages }
  );
}

export function uploadText(kbId: string, title: string, text: string) {
  return request<DocumentInfo>(
    "POST",
    `/api/knowledge-bases/${kbId}/documents/text`,
    { title, text }
  );
}

export function getDocument(kbId: string, docId: string, signal?: AbortSignal) {
  return request<DocumentDetail>(
    "GET",
    `/api/knowledge-bases/${kbId}/documents/${docId}`,
    undefined,
    signal
  );
}

export function deleteDocument(kbId: string, docId: string) {
  return request<{ status: string; id: string }>(
    "DELETE",
    `/api/knowledge-bases/${kbId}/documents/${docId}`
  );
}

export function reprocessDocument(kbId: string, docId: string) {
  return request<DocumentInfo>(
    "POST",
    `/api/knowledge-bases/${kbId}/documents/${docId}/reprocess`
  );
}

// ==================== Chunks ====================

export function listChunks(
  kbId: string,
  docId: string,
  signal?: AbortSignal
) {
  return request<ChunkList>(
    "GET",
    `/api/knowledge-bases/${kbId}/documents/${docId}/chunks`,
    undefined,
    signal
  );
}
