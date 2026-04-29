/** Chat API types - mirrors backend/api/schemas/chat.py */

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  agent_config_id?: string | null;
}

export interface ToolCall {
  name: string;
  input: Record<string, unknown>;
  output: string;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  tool_calls: ToolCall[];
  needs_approval: boolean;
  approval_info: { name: string; input: Record<string, unknown> }[] | null;
}

/** Session API types - mirrors backend/api/schemas/session.py */

export interface SessionInfo {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  agent_config_id: string | null;
  agent_name: string | null;
}

export interface SessionList {
  sessions: SessionInfo[];
  total: number;
}

export interface MessageInfo {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

export interface MessageList {
  messages: MessageInfo[];
  total: number;
}

/** Skills API types */

export interface SkillInfo {
  name: string;
  description: string;
  version: string;
  source: string;
  allowed_tools: string[];
}

export interface SkillsListResponse {
  skills: SkillInfo[];
  count: number;
}

/** Channel API types - mirrors backend/api/channel.py */

export interface ChannelInfo {
  id: string;
  platform: string;
  name: string;
  config: Record<string, unknown>;
  enabled: boolean;
  allowed_senders: string[];
  created_at: string;
  configured: boolean;
  running: boolean;
}

export interface CreateChannelRequest {
  name: string;
  platform: string;
  config?: Record<string, unknown>;
  allowed_senders?: string[];
}

export interface ChannelStartStopResponse {
  success: boolean;
  channel_id: string;
}

export interface UpdateSendersRequest {
  allowed_senders: string[];
}

export interface UpdateSendersResponse {
  success: boolean;
  allowed_senders: string[];
}

export interface WeChatQRCodeResponse {
  qrcode: string;
  qrcode_img_content: string;
}

export interface WeChatLoginStatus {
  status: "wait" | "scaned" | "confirmed" | "expired";
  bot_token?: string;
  ilink_bot_id?: string;
  ilink_user_id?: string;
}

export interface ChannelSessionInfo {
  id: number;
  channel_id: string;
  im_conversation_id: string;
  agent_session_id: string;
  context_data: Record<string, unknown> | null;
  last_active_at: string;
}

/** Agent Config API types - mirrors backend/api/schemas/agent_config.py */

export interface AgentConfigInfo {
  id: string;
  name: string;
  description: string;
  model_id: string;
  max_tokens: number;
  builtin_tools: string[];
  skills: string[];
  mcp_servers: string[];
  knowledge_base_ids: string[];
  max_iterations: number;
  tool_timeout: number;
  auto_approve_safe: boolean;
  system_prompt_overrides: Record<string, string>;
  avatar: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigList {
  configs: AgentConfigInfo[];
  total: number;
}

export interface CreateAgentConfigRequest {
  name: string;
  description?: string;
  model_id?: string;
  max_tokens?: number;
  builtin_tools?: string[];
  skills?: string[];
  mcp_servers?: string[];
  knowledge_base_ids?: string[];
  max_iterations?: number;
  tool_timeout?: number;
  auto_approve_safe?: boolean;
  system_prompt_overrides?: Record<string, string>;
  avatar?: string;
}

export type UpdateAgentConfigRequest = Partial<CreateAgentConfigRequest>;

/** Tools API types */

export interface ToolInfo {
  name: string;
  description: string;
  source: string;
  permission: string;
}

export interface SkillItem {
  name: string;
  description: string;
  source: string;
}

export interface McpServerItem {
  name: string;
  tools_count: number;
  connected: boolean;
}

export interface ToolsListResponse {
  tools: ToolInfo[];
  builtin: ToolInfo[];
  mcp: ToolInfo[];
  skills: SkillItem[];
  mcp_servers: McpServerItem[];
}

/** MCP Server Management API types */

export interface MCPServerInfo {
  id: string;
  name: string;
  transport: "stdio" | "http";
  command: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  headers: Record<string, string>;
  enabled: boolean;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface MCPServerList {
  servers: MCPServerInfo[];
  total: number;
}

export interface CreateMCPServerRequest {
  name: string;
  transport?: "stdio" | "http";
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  enabled?: boolean;
  description?: string;
}

export type UpdateMCPServerRequest = Partial<CreateMCPServerRequest>;

export interface MCPServerStatusInfo {
  name: string;
  connected: boolean;
  error: string | null;
  tools: { name: string; description: string; input_schema: Record<string, unknown> }[];
  resources: { uri: string; name: string; description: string; mime_type: string }[];
  prompts: { name: string; description: string; arguments: Record<string, unknown>[] }[];
}

/** Knowledge Base API types */

export interface KnowledgeBaseInfo {
  id: string;
  name: string;
  description: string;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseList {
  knowledge_bases: KnowledgeBaseInfo[];
  total: number;
}

export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface UpdateKnowledgeBaseRequest {
  name?: string;
  description?: string;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface DocumentInfo {
  id: string;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  source_uri: string;
  mime_type: string;
  file_size: number;
  status: string;
  error_message: string;
  chunk_count: number;
  embedding_status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  documents: DocumentInfo[];
  total: number;
}

export interface DocumentDetail extends DocumentInfo {
  raw_text_preview: string;
}

export interface ChunkInfo {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  char_count: number;
  token_count: number;
  section_headers: string[];
  metadata: Record<string, unknown>;
}

export interface ChunkList {
  chunks: ChunkInfo[];
  total: number;
}
