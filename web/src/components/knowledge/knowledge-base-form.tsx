"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type {
  KnowledgeBaseInfo,
  CreateKnowledgeBaseRequest,
} from "@/lib/api/types";

interface KnowledgeBaseFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: KnowledgeBaseInfo;
  onSubmit: (data: CreateKnowledgeBaseRequest) => Promise<void>;
}

export function KnowledgeBaseForm({
  open,
  onOpenChange,
  initialData,
  onSubmit,
}: KnowledgeBaseFormProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [chunkSize, setChunkSize] = useState(initialData?.chunk_size ?? 1000);
  const [chunkOverlap, setChunkOverlap] = useState(
    initialData?.chunk_overlap ?? 200
  );
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({ name, description, chunk_size: chunkSize, chunk_overlap: chunkOverlap });
      onOpenChange(false);
      setName("");
      setDescription("");
      setChunkSize(1000);
      setChunkOverlap(200);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {initialData ? "编辑知识库" : "创建知识库"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">名称</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="知识库名称"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">描述</label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="可选描述"
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">
                分块大小（字符）
              </label>
              <Input
                type="number"
                min={100}
                max={10000}
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                重叠字符数
              </label>
              <Input
                type="number"
                min={0}
                max={2000}
                value={chunkOverlap}
                onChange={(e) => setChunkOverlap(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? "提交中..." : initialData ? "更新" : "创建"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
