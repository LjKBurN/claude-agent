"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { updateSenders } from "@/lib/api/channels";
import { toast } from "sonner";

interface SenderWhitelistProps {
  channelId: string;
  senders: string[];
  onChange: () => void;
}

export function SenderWhitelist({
  channelId,
  senders,
  onChange,
}: SenderWhitelistProps) {
  const [newSender, setNewSender] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleAdd() {
    const val = newSender.trim();
    if (!val || senders.includes(val)) return;
    setSaving(true);
    try {
      await updateSenders(channelId, {
        allowed_senders: [...senders, val],
      });
      setNewSender("");
      toast.success("已添加");
      onChange();
    } catch (err) {
      toast.error(`添加失败: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(sender: string) {
    setSaving(true);
    try {
      await updateSenders(channelId, {
        allowed_senders: senders.filter((s) => s !== sender),
      });
      toast.success("已删除");
      onChange();
    } catch (err) {
      toast.error(`删除失败: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">白名单</h3>

      {senders.length === 0 ? (
        <p className="text-sm text-muted-foreground">未设置白名单（允许所有发送者）</p>
      ) : (
        <ul className="space-y-2">
          {senders.map((sender) => (
            <li
              key={sender}
              className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
            >
              <span className="font-mono text-xs">{sender}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => handleRemove(sender)}
                disabled={saving}
              >
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-2">
        <input
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="输入发送者 ID，如 wxid_xxx"
          value={newSender}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setNewSender(e.target.value)
          }
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
            e.key === "Enter" && handleAdd()
          }
        />
        <Button
          size="sm"
          onClick={handleAdd}
          disabled={saving || !newSender.trim()}
          className="gap-1"
        >
          <Plus className="h-3.5 w-3.5" />
          添加
        </Button>
      </div>
    </div>
  );
}
