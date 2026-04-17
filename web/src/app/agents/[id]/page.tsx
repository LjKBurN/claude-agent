"use client";

import { useRouter, useParams } from "next/navigation";
import { AgentForm } from "@/components/agent/agent-form";
import { useAgentConfig } from "@/lib/hooks/use-agent-configs";
import { updateAgentConfig } from "@/lib/api/agent-configs";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import type { CreateAgentConfigRequest } from "@/lib/api/types";

export default function EditAgentPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const { config, isLoading } = useAgentConfig(id);

  async function handleSubmit(data: CreateAgentConfigRequest) {
    try {
      await updateAgentConfig(id, data);
      toast.success(`Agent "${data.name}" 已更新`);
      router.push("/agents");
    } catch (err) {
      toast.error(`更新失败: ${(err as Error).message}`);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载中...
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        Agent 不存在
      </div>
    );
  }

  return <AgentForm initialData={config} onSubmit={handleSubmit} submitLabel="保存更改" />;
}
