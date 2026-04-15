"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Loader2, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getWeChatQRCode, getWeChatLoginStatus } from "@/lib/api/channels";
import { toast } from "sonner";

interface QRLoginProps {
  channelId: string;
  onLoginSuccess: () => void;
}

export function QRLogin({ channelId, onLoginSuccess }: QRLoginProps) {
  const [qrPageUrl, setQrPageUrl] = useState<string | null>(null);
  const [qrId, setQrId] = useState<string | null>(null);
  const [status, setStatus] = useState<
    "idle" | "loading" | "waiting" | "scaned" | "confirmed" | "expired" | "error"
  >("idle");
  const abortRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    abortRef.current?.abort();
  }, []);

  const startPolling = useCallback(
    (qrcode: string) => {
      stopPolling();
      pollTimerRef.current = setInterval(async () => {
        try {
          const controller = new AbortController();
          abortRef.current = controller;
          const res = await getWeChatLoginStatus(
            channelId,
            qrcode,
            controller.signal,
          );
          if (res.status === "scaned") {
            setStatus("scaned");
          } else if (res.status === "confirmed") {
            setStatus("confirmed");
            stopPolling();
            toast.success("微信登录成功");
            onLoginSuccess();
          } else if (res.status === "expired") {
            setStatus("expired");
            stopPolling();
          }
        } catch {
          // Ignore abort errors
        }
      }, 3000);
    },
    [channelId, onLoginSuccess, stopPolling],
  );

  const fetchQRCode = useCallback(async () => {
    setStatus("loading");
    stopPolling();
    try {
      const res = await getWeChatQRCode(channelId);
      setQrPageUrl(res.qrcode_img_content);
      setQrId(res.qrcode);
      setStatus("waiting");
      startPolling(res.qrcode);
    } catch (err) {
      setStatus("error");
      toast.error(`获取二维码失败: ${(err as Error).message}`);
    }
  }, [channelId, startPolling, stopPolling]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">微信登录</h3>
        {qrPageUrl && (
          <Button variant="ghost" size="sm" onClick={fetchQRCode}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
            刷新
          </Button>
        )}
      </div>

      <div className="flex flex-col items-center gap-3 rounded-lg border p-4">
        {status === "idle" && (
          <Button onClick={fetchQRCode}>获取登录二维码</Button>
        )}
        {status === "loading" && (
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        )}
        {qrPageUrl && (status === "waiting" || status === "scaned") && (
          <>
            <iframe
              src={qrPageUrl}
              className="h-56 w-56 rounded border-0"
              sandbox="allow-scripts"
              title="WeChat QR Code"
            />
            <p className="text-sm text-muted-foreground">
              {status === "waiting"
                ? "请用微信扫码登录"
                : "已扫码，请在手机上确认"}
            </p>
            <a
              href={qrPageUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground underline hover:text-foreground"
            >
              <ExternalLink className="h-3 w-3" />
              在新窗口打开
            </a>
          </>
        )}
        {status === "confirmed" && (
          <p className="text-sm font-medium text-green-600">登录成功！</p>
        )}
        {status === "expired" && (
          <div className="text-center space-y-2">
            <p className="text-sm text-muted-foreground">二维码已过期</p>
            <Button size="sm" onClick={fetchQRCode}>
              重新获取
            </Button>
          </div>
        )}
        {status === "error" && (
          <div className="text-center space-y-2">
            <p className="text-sm text-destructive">获取二维码失败</p>
            <Button size="sm" onClick={fetchQRCode}>
              重试
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
