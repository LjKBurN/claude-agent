"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, BookOpen, Trash2, Pencil, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { useKnowledgeBases } from "@/lib/hooks/use-knowledge-bases";
import {
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
} from "@/lib/api/knowledge-base";
import { KnowledgeBaseForm } from "@/components/knowledge/knowledge-base-form";
import type { KnowledgeBaseInfo, CreateKnowledgeBaseRequest } from "@/lib/api/types";

export default function KnowledgePage() {
  const router = useRouter();
  const { knowledgeBases, isLoading, mutate } = useKnowledgeBases();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBaseInfo | undefined>();
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleCreate(data: CreateKnowledgeBaseRequest) {
    await createKnowledgeBase(data);
    toast.success(`已创建知识库 "${data.name}"`);
    mutate();
  }

  async function handleEdit(data: CreateKnowledgeBaseRequest) {
    if (!editing) return;
    await updateKnowledgeBase(editing.id, data);
    toast.success(`已更新 "${data.name}"`);
    setEditing(undefined);
    mutate();
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`确定要删除知识库 "${name}" 吗？所有文档和分块将被删除。`)) return;
    setDeleting(id);
    try {
      await deleteKnowledgeBase(id);
      toast.success(`已删除 "${name}"`);
      mutate();
    } catch (err) {
      toast.error(`删除失败: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">知识库管理</h2>
          <p className="text-sm text-muted-foreground">
            创建知识库，上传文档构建 RAG 能力
          </p>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(undefined);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          创建知识库
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      ) : knowledgeBases.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <BookOpen className="mb-3 h-10 w-10" />
          <p className="text-sm">暂无知识库</p>
          <p className="text-xs">点击上方按钮创建第一个</p>
        </div>
      ) : (
        <div className="space-y-3">
          {knowledgeBases.map((kb) => (
            <Card
              key={kb.id}
              className="cursor-pointer transition-colors hover:bg-accent/50"
              onClick={() => router.push(`/knowledge/${kb.id}`)}
            >
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{kb.name}</span>
                    </div>
                    {kb.description && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {kb.description}
                      </p>
                    )}
                    <div className="mt-1 flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px]">
                        {kb.document_count} 文档
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {kb.total_chunks} 分块
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        分块: {kb.chunk_size} / 重叠: {kb.chunk_overlap}
                      </span>
                    </div>
                  </div>
                  <div
                    className="flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => {
                        setEditing(kb);
                        setFormOpen(true);
                      }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => handleDelete(kb.id, kb.name)}
                      disabled={deleting === kb.id}
                    >
                      {deleting === kb.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <KnowledgeBaseForm
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(undefined);
        }}
        initialData={editing}
        onSubmit={editing ? handleEdit : handleCreate}
      />
    </div>
  );
}
