"use client";

import { useCallback, useState } from "react";
import { Upload, Link, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { uploadDocuments, uploadUrl, uploadText } from "@/lib/api/knowledge-base";

interface DocumentUploadProps {
  kbId: string;
  onUploaded: () => void;
}

const ACCEPTED_EXTENSIONS = ".md,.pdf,.txt,.docx,.html,.csv,.json";

export function DocumentUpload({ kbId, onUploaded }: DocumentUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [url, setUrl] = useState("");
  const [crawlDepth, setCrawlDepth] = useState(0);
  const [textTitle, setTextTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const handleFileUpload = useCallback(
    async (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      if (fileArray.length === 0) return;

      setUploading(true);
      try {
        await uploadDocuments(kbId, fileArray);
        toast.success(`已上传 ${fileArray.length} 个文件，正在处理中...`);
        onUploaded();
      } catch (err) {
        toast.error(`上传失败: ${(err as Error).message}`);
      } finally {
        setUploading(false);
      }
    },
    [kbId, onUploaded]
  );

  const handleUrlSubmit = async () => {
    if (!url.trim()) return;
    setUploading(true);
    try {
      await uploadUrl(kbId, url, crawlDepth);
      toast.success("URL 已提交，正在爬取处理...");
      setUrl("");
      onUploaded();
    } catch (err) {
      toast.error(`URL 导入失败: ${(err as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleTextSubmit = async () => {
    if (!textContent.trim()) return;
    setUploading(true);
    try {
      await uploadText(kbId, textTitle || "文本输入", textContent);
      toast.success("文本已提交，正在处理...");
      setTextTitle("");
      setTextContent("");
      onUploaded();
    } catch (err) {
      toast.error(`文本导入失败: ${(err as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Tabs defaultValue="file" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="file" className="gap-1.5">
          <Upload className="h-3.5 w-3.5" />
          文件上传
        </TabsTrigger>
        <TabsTrigger value="url" className="gap-1.5">
          <Link className="h-3.5 w-3.5" />
          URL 导入
        </TabsTrigger>
        <TabsTrigger value="text" className="gap-1.5">
          <FileText className="h-3.5 w-3.5" />
          文本输入
        </TabsTrigger>
      </TabsList>

      <TabsContent value="file" className="mt-3">
        <div
          className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFileUpload(e.dataTransfer.files);
          }}
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.multiple = true;
            input.accept = ACCEPTED_EXTENSIONS;
            input.onchange = () => {
              if (input.files) handleFileUpload(input.files);
            };
            input.click();
          }}
        >
          {uploading ? (
            <Loader2 className="mb-2 h-8 w-8 animate-spin text-muted-foreground" />
          ) : (
            <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
          )}
          <p className="text-sm text-muted-foreground">
            {uploading
              ? "上传中..."
              : "拖拽文件到此处，或点击选择文件"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            支持 md, pdf, txt, docx, html, csv, json
          </p>
        </div>
      </TabsContent>

      <TabsContent value="url" className="mt-3 space-y-3">
        <Input
          placeholder="输入网页地址"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          type="url"
        />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground">爬取深度:</label>
            <select
              className="rounded border px-2 py-1 text-xs"
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(Number(e.target.value))}
            >
              <option value={0}>仅当前页</option>
              <option value={1}>1 层子链接</option>
              <option value={2}>2 层子链接</option>
            </select>
          </div>
          <Button
            size="sm"
            onClick={handleUrlSubmit}
            disabled={uploading || !url.trim()}
          >
            {uploading ? "提交中..." : "导入"}
          </Button>
        </div>
      </TabsContent>

      <TabsContent value="text" className="mt-3 space-y-3">
        <Input
          placeholder="标题（可选）"
          value={textTitle}
          onChange={(e) => setTextTitle(e.target.value)}
        />
        <Textarea
          placeholder="输入或粘贴文本内容..."
          value={textContent}
          onChange={(e) => setTextContent(e.target.value)}
          rows={6}
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={handleTextSubmit}
            disabled={uploading || !textContent.trim()}
          >
            {uploading ? "提交中..." : "导入"}
          </Button>
        </div>
      </TabsContent>
    </Tabs>
  );
}
