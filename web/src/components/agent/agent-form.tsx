"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listTools } from "@/lib/api/tools";
import { listKnowledgeBases } from "@/lib/api/knowledge-base";
import type {
  AgentConfigInfo,
  CreateAgentConfigRequest,
  KnowledgeBaseInfo,
  McpServerItem,
  SkillItem,
  ToolInfo,
} from "@/lib/api/types";

const MODEL_OPTIONS = [
  { value: "claude-sonnet-4-6-20250514", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "claude-opus-4-6-20250424", label: "Claude Opus 4.6" },
];

const AVATAR_OPTIONS = ["🤖", "📝", "🔧", "💻", "🔍", "📊", "🧪", "🚀"];

interface AgentFormProps {
  initialData?: AgentConfigInfo;
  onSubmit: (data: CreateAgentConfigRequest) => Promise<void>;
  submitLabel: string;
}

export function AgentForm({ initialData, onSubmit, submitLabel }: AgentFormProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [modelId, setModelId] = useState(initialData?.model_id ?? "claude-sonnet-4-6-20250514");
  const [maxTokens, setMaxTokens] = useState(initialData?.max_tokens ?? 8000);
  const [builtinTools, setBuiltinTools] = useState<string[]>(initialData?.builtin_tools ?? []);
  const [selectedSkills, setSelectedSkills] = useState<string[]>(initialData?.skills ?? []);
  const [selectedMcpServers, setSelectedMcpServers] = useState<string[]>(
    initialData?.mcp_servers ?? []
  );
  const [selectedKnowledgeBases, setSelectedKnowledgeBases] = useState<string[]>(
    initialData?.knowledge_base_ids ?? []
  );
  const [maxIterations, setMaxIterations] = useState(initialData?.max_iterations ?? 20);
  const [toolTimeout, setToolTimeout] = useState(initialData?.tool_timeout ?? 120);
  const [systemPromptOverrides, setSystemPromptOverrides] = useState<string>(
    initialData?.system_prompt_overrides
      ? Object.entries(initialData.system_prompt_overrides)
          .map(([k, v]) => `${k}: ${v}`)
          .join("\n")
      : ""
  );
  const [avatar, setAvatar] = useState<string | null>(initialData?.avatar ?? null);
  const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);
  const [availableSkills, setAvailableSkills] = useState<SkillItem[]>([]);
  const [availableMcpServers, setAvailableMcpServers] = useState<McpServerItem[]>([]);
  const [availableKnowledgeBases, setAvailableKnowledgeBases] = useState<KnowledgeBaseInfo[]>([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listTools()
      .then((res) => {
        setAvailableTools(res.builtin);
        setAvailableSkills(res.skills);
        setAvailableMcpServers(res.mcp_servers);
        // 仅新建时默认全选；编辑时保留用户原始选择（包括空数组）
        if (!initialData) {
          setBuiltinTools(res.builtin.map((t) => t.name));
          setSelectedSkills(res.skills.map((s) => s.name));
          setSelectedMcpServers(res.mcp_servers.map((s) => s.name));
        }
      })
      .catch(() => {})
      .finally(() => setToolsLoading(false));

    listKnowledgeBases()
      .then((res) => setAvailableKnowledgeBases(res.knowledge_bases))
      .catch(() => {});
  }, [initialData]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const promptOverrides: Record<string, string> = {};
      if (systemPromptOverrides.trim()) {
        for (const line of systemPromptOverrides.split("\n")) {
          const idx = line.indexOf(":");
          if (idx > 0) {
            promptOverrides[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
          }
        }
      }

      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        model_id: modelId,
        max_tokens: maxTokens,
        builtin_tools: builtinTools,
        skills: selectedSkills,
        mcp_servers: selectedMcpServers,
        knowledge_base_ids: selectedKnowledgeBases,
        max_iterations: maxIterations,
        tool_timeout: toolTimeout,
        system_prompt_overrides: promptOverrides,
        avatar: avatar ?? undefined,
      });
    } finally {
      setSubmitting(false);
    }
  }

  function toggleTool(toolName: string) {
    setBuiltinTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  }

  function toggleSkill(skillName: string) {
    setSelectedSkills((prev) =>
      prev.includes(skillName) ? prev.filter((s) => s !== skillName) : [...prev, skillName]
    );
  }

  function toggleMcpServer(serverName: string) {
    setSelectedMcpServers((prev) =>
      prev.includes(serverName) ? prev.filter((s) => s !== serverName) : [...prev, serverName]
    );
  }

  function toggleKnowledgeBase(kbId: string) {
    setSelectedKnowledgeBases((prev) =>
      prev.includes(kbId) ? prev.filter((id) => id !== kbId) : [...prev, kbId]
    );
  }

  const inputClass =
    "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-2xl space-y-6 p-6">
      {/* 基本信息 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">基本信息</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">名称 *</label>
              <input
                className={inputClass}
                placeholder="例如：Code Reviewer"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="w-32 space-y-2">
              <label className="text-sm font-medium">头像</label>
              <div className="flex flex-wrap gap-1">
                {AVATAR_OPTIONS.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    className={`flex h-8 w-8 items-center justify-center rounded-md border text-sm transition-colors ${
                      avatar === emoji ? "border-primary bg-primary/10" : "border-input hover:bg-accent"
                    }`}
                    onClick={() => setAvatar(avatar === emoji ? null : emoji)}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">描述</label>
            <input
              className={inputClass}
              placeholder="Agent 的功能描述"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* 模型设置 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">模型设置</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">模型</label>
              <select
                className={inputClass}
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
              >
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="w-32 space-y-2">
              <label className="text-sm font-medium">Max Tokens</label>
              <input
                type="number"
                className={inputClass}
                value={maxTokens}
                min={100}
                max={64000}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 工具配置 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">工具配置</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {toolsLoading ? (
            <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              加载工具列表...
            </div>
          ) : (
            <>
              {/* 内置工具 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">内置工具</label>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {builtinTools.length} / {availableTools.length}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() =>
                        setBuiltinTools(
                          builtinTools.length === availableTools.length
                            ? []
                            : availableTools.map((t) => t.name)
                        )
                      }
                    >
                      {builtinTools.length === availableTools.length ? "全不选" : "全选"}
                    </Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {availableTools.map((tool) => (
                    <label
                      key={tool.name}
                      className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                        builtinTools.includes(tool.name)
                          ? "border-primary bg-primary/5"
                          : "border-input hover:bg-accent"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 rounded border-input"
                        checked={builtinTools.includes(tool.name)}
                        onChange={() => toggleTool(tool.name)}
                      />
                      <div>
                        <div className="font-medium">{tool.name}</div>
                        <div className="text-[10px] text-muted-foreground line-clamp-1">
                          {tool.description}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Skills */}
              {availableSkills.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Skills</label>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {selectedSkills.length} / {availableSkills.length}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() =>
                          setSelectedSkills(
                            selectedSkills.length === availableSkills.length
                              ? []
                              : availableSkills.map((s) => s.name)
                          )
                        }
                      >
                        {selectedSkills.length === availableSkills.length ? "全不选" : "全选"}
                      </Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {availableSkills.map((skill) => (
                      <label
                        key={skill.name}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                          selectedSkills.includes(skill.name)
                            ? "border-primary bg-primary/5"
                            : "border-input hover:bg-accent"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 rounded border-input"
                          checked={selectedSkills.includes(skill.name)}
                          onChange={() => toggleSkill(skill.name)}
                        />
                        <div>
                          <div className="font-medium">{skill.name}</div>
                          <div className="text-[10px] text-muted-foreground line-clamp-1">
                            {skill.description}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* MCP Servers */}
              {availableMcpServers.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">MCP Servers</label>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {selectedMcpServers.length} / {availableMcpServers.length}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() =>
                          setSelectedMcpServers(
                            selectedMcpServers.length === availableMcpServers.length
                              ? []
                              : availableMcpServers.map((s) => s.name)
                          )
                        }
                      >
                        {selectedMcpServers.length === availableMcpServers.length ? "全不选" : "全选"}
                      </Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {availableMcpServers.map((server) => (
                      <label
                        key={server.name}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                          selectedMcpServers.includes(server.name)
                            ? "border-primary bg-primary/5"
                            : "border-input hover:bg-accent"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 rounded border-input"
                          checked={selectedMcpServers.includes(server.name)}
                          onChange={() => toggleMcpServer(server.name)}
                        />
                        <div>
                          <div className="font-medium">{server.name}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {server.tools_count} tools
                            {!server.connected && " (未连接)"}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Knowledge Bases */}
              {availableKnowledgeBases.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">知识库</label>
                  <div className="grid grid-cols-2 gap-2">
                    {availableKnowledgeBases.map((kb) => (
                      <label
                        key={kb.id}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                          selectedKnowledgeBases.includes(kb.id)
                            ? "border-primary bg-primary/5"
                            : "border-input hover:bg-accent"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 rounded border-input"
                          checked={selectedKnowledgeBases.includes(kb.id)}
                          onChange={() => toggleKnowledgeBase(kb.id)}
                        />
                        <div>
                          <div className="font-medium">{kb.name}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {kb.document_count} 文档 · {kb.total_chunks} 分块
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 高级设置 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">高级设置</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">最大迭代次数</label>
              <input
                type="number"
                className={inputClass}
                value={maxIterations}
                min={1}
                max={100}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
              />
            </div>
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">工具超时 (秒)</label>
              <input
                type="number"
                className={inputClass}
                value={toolTimeout}
                min={10}
                max={600}
                onChange={(e) => setToolTimeout(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">
              System Prompt 覆盖
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                每行一条，格式：key: value
              </span>
            </label>
            <textarea
              className={`${inputClass} min-h-[80px] resize-y`}
              placeholder={"custom_instruction: 始终使用中文回答\nmax_bash_commands: 5"}
              value={systemPromptOverrides}
              onChange={(e) => setSystemPromptOverrides(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* 提交 */}
      <Button type="submit" className="w-full" disabled={submitting || !name.trim()}>
        {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {submitLabel}
      </Button>
    </form>
  );
}
