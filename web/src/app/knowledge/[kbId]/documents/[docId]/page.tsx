"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getDocument, listChunks } from "@/lib/api/knowledge-base";
import { ChunkPreview } from "@/components/knowledge/chunk-preview";

interface Props {
  params: Promise<{ kbId: string; docId: string }>;
}

export default function DocumentDetailPage({ params }: Props) {
  const [resolvedParams, setResolvedParams] = useState<{
    kbId: string;
    docId: string;
  } | null>(null);

  params.then(setResolvedParams);

  const kbId = resolvedParams?.kbId ?? "";
  const docId = resolvedParams?.docId ?? "";

  const { data: doc, isLoading: docLoading } = useSWR(
    kbId && docId ? `/api/knowledge-bases/${kbId}/documents/${docId}` : null,
    () => getDocument(kbId, docId)
  );

  const { data: chunkData, isLoading: chunksLoading } = useSWR(
    kbId && docId ? `/api/knowledge-bases/${kbId}/documents/${docId}/chunks` : null,
    () => listChunks(kbId, docId),
    { refreshInterval: doc?.status === "processing" || doc?.status === "pending" ? 3000 : 0 }
  );

  const router = useRouter();

  if (!resolvedParams) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => router.push(`/knowledge/${kbId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-lg font-semibold">
            {docLoading ? "加载中..." : doc?.title}
          </h2>
          {doc && (
            <div className="mt-1 flex items-center gap-2">
              <Badge
                variant={
                  doc.status === "completed"
                    ? "default"
                    : doc.status === "failed"
                      ? "destructive"
                      : "secondary"
                }
                className="text-[10px]"
              >
                {doc.status === "processing" && (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                )}
                {doc.status === "pending"
                  ? "待处理"
                  : doc.status === "processing"
                    ? "处理中"
                    : doc.status === "completed"
                      ? "已完成"
                      : "失败"}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {doc.source_type === "file"
                  ? `文件 · ${(doc.file_size / 1024).toFixed(1)} KB`
                  : doc.source_type === "url"
                    ? `URL · ${doc.source_uri}`
                    : "文本输入"}
              </span>
              {doc.chunk_count > 0 && (
                <span className="text-xs text-muted-foreground">
                  {doc.chunk_count} 分块
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {doc?.raw_text_preview && (
        <div className="rounded-lg border p-3">
          <div className="mb-1 text-xs font-medium text-muted-foreground">
            原始文本预览
          </div>
          <pre className="line-clamp-6 whitespace-pre-wrap break-words text-xs text-foreground/80">
            {doc.raw_text_preview}
            {doc.raw_text_preview.length >= 500 && "..."}
          </pre>
        </div>
      )}

      <div className="text-sm font-medium">
        分块结果
        {chunkData && (
          <span className="ml-2 text-muted-foreground">
            ({chunkData.total} chunks)
          </span>
        )}
      </div>

      {chunksLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : (
        <ChunkPreview chunks={chunkData?.chunks ?? []} />
      )}
    </div>
  );
}
