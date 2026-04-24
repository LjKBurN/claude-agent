"use client";

import { Loader2, Trash2, RefreshCw, FileText, Link, Type } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { DocumentInfo } from "@/lib/api/types";

interface DocumentListProps {
  documents: DocumentInfo[];
  kbId: string;
  onDelete: (docId: string, title: string) => void;
  onReprocess: (docId: string) => void;
  onClick: (docId: string) => void;
  operating?: string | null;
}

const STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "待处理", variant: "outline" },
  processing: { label: "处理中", variant: "secondary" },
  completed: { label: "已完成", variant: "default" },
  failed: { label: "失败", variant: "destructive" },
};

const SOURCE_ICON: Record<string, typeof FileText> = {
  file: FileText,
  url: Link,
  text: Type,
};

export function DocumentList({
  documents,
  kbId,
  onDelete,
  onReprocess,
  onClick,
  operating,
}: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <FileText className="mb-3 h-10 w-10" />
        <p className="text-sm">暂无文档</p>
        <p className="text-xs">通过上方上传文件、导入 URL 或输入文本</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const status = STATUS_MAP[doc.status] ?? STATUS_MAP.pending;
        const SourceIcon = SOURCE_ICON[doc.source_type] ?? FileText;
        const isOperating = operating === doc.id;

        return (
          <Card
            key={doc.id}
            className="cursor-pointer transition-colors hover:bg-accent/50"
            onClick={() => onClick(doc.id)}
          >
            <CardContent className="flex items-center justify-between py-3">
              <div className="flex-1 overflow-hidden">
                <div className="flex items-center gap-2">
                  <SourceIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate text-sm font-medium">
                    {doc.title}
                  </span>
                  <Badge variant={status.variant} className="text-[10px]">
                    {doc.status === "processing" && (
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    )}
                    {status.label}
                  </Badge>
                  {doc.chunk_count > 0 && (
                    <Badge variant="outline" className="text-[10px]">
                      {doc.chunk_count} chunks
                    </Badge>
                  )}
                </div>
                {doc.error_message && (
                  <p className="mt-1 truncate text-xs text-destructive">
                    {doc.error_message}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => onReprocess(doc.id)}
                  disabled={isOperating}
                  title="重新处理"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${isOperating ? "animate-spin" : ""}`}
                  />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => onDelete(doc.id, doc.title)}
                  disabled={isOperating}
                  title="删除"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
