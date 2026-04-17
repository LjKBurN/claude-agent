"use client";

import { useRouter } from "next/navigation";
import { AgentForm } from "@/components/agent/agent-form";
import { createAgentConfig } from "@/lib/api/agent-configs";
import { toast } from "sonner";
import type { CreateAgentConfigRequest } from "@/lib/api/types";

export default function NewAgentPage() {
  const router = useRouter();

  async function handleSubmit(data: CreateAgentConfigRequest) {
    try {
      await createAgentConfig(data);
      toast.success(`Agent "${data.name}" 创建成功`);
      router.push("/agents");
    } catch (err) {
      toast.error(`创建失败: ${(err as Error).message}`);
    }
  }

  return <AgentForm onSubmit={handleSubmit} submitLabel="创建 Agent" />;
}
