"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type { ChunkInfo } from "@/lib/api/types";

interface ChunkPreviewProps {
  chunks: ChunkInfo[];
}

export function ChunkPreview({ chunks }: ChunkPreviewProps) {
  if (chunks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <p className="text-sm">暂无分块数据</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[600px]">
      <div className="space-y-3 pr-4">
        {chunks.map((chunk) => (
          <div
            key={chunk.id}
            className="rounded-lg border p-3"
          >
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                #{chunk.chunk_index}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {chunk.char_count} 字 / {chunk.token_count} tokens
              </span>
              {chunk.section_headers.length > 0 && (
                <div className="flex gap-1">
                  {chunk.section_headers.map((h, i) => (
                    <Badge
                      key={i}
                      variant="secondary"
                      className="text-[10px]"
                    >
                      {h}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-foreground/90">
              {chunk.content}
            </pre>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
