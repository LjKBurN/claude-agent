"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  getKnowledgeBase,
  listDocuments,
  deleteDocument,
  reprocessDocument,
} from "@/lib/api/knowledge-base";
import { DocumentUpload } from "@/components/knowledge/document-upload";
import { DocumentList } from "@/components/knowledge/document-list";

interface Props {
  params: Promise<{ kbId: string }>;
}

export default function KnowledgeBaseDetailPage({ params }: Props) {
  const [resolvedParams, setResolvedParams] = useState<{ kbId: string } | null>(null);
  const [operating, setOperating] = useState<string | null>(null);

  params.then(setResolvedParams);

  const kbId = resolvedParams?.kbId ?? "";

  const {
    data: kb,
    isLoading: kbLoading,
  } = useSWR(kbId ? `/api/knowledge-bases/${kbId}` : null, () =>
    getKnowledgeBase(kbId)
  );

  const {
    data: docData,
    isLoading: docsLoading,
    mutate: mutateDocs,
  } = useSWR(kbId ? `/api/knowledge-bases/${kbId}/documents` : null, () =>
    listDocuments(kbId)
  );

  const router = useRouter();

  const handleDelete = useCallback(
    async (docId: string, title: string) => {
      if (!confirm(`确定要删除 "${title}" 吗？`)) return;
      setOperating(docId);
      try {
        await deleteDocument(kbId, docId);
        toast.success(`已删除 "${title}"`);
        mutateDocs();
      } catch (err) {
        toast.error(`删除失败: ${(err as Error).message}`);
      } finally {
        setOperating(null);
      }
    },
    [kbId, mutateDocs]
  );

  const handleReprocess = useCallback(
    async (docId: string) => {
      setOperating(docId);
      try {
        await reprocessDocument(kbId, docId);
        toast.success("已提交重新处理");
        mutateDocs();
      } catch (err) {
        toast.error(`重新处理失败: ${(err as Error).message}`);
      } finally {
        setOperating(null);
      }
    },
    [kbId, mutateDocs]
  );

  const handleDocClick = useCallback(
    (docId: string) => {
      router.push(`/knowledge/${kbId}/documents/${docId}`);
    },
    [router, kbId]
  );

  if (!resolvedParams) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => router.push("/knowledge")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-lg font-semibold">
            {kbLoading ? "加载中..." : kb?.name}
          </h2>
          {kb?.description && (
            <p className="text-sm text-muted-foreground">{kb.description}</p>
          )}
        </div>
      </div>

      <DocumentUpload kbId={kbId} onUploaded={() => mutateDocs()} />

      <div className="text-sm font-medium">
        文档列表
        {docData && (
          <span className="ml-2 text-muted-foreground">({docData.total})</span>
        )}
      </div>

      {docsLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : (
        <DocumentList
          documents={docData?.documents ?? []}
          kbId={kbId}
          onDelete={handleDelete}
          onReprocess={handleReprocess}
          onClick={handleDocClick}
          operating={operating}
        />
      )}
    </div>
  );
}
