# 技术架构

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端语言 | Python 3.10+ |
| 后端框架 | FastAPI |
| Agent | Agent Core (LLM + Tools + Loop) |
| 数据库 | PostgreSQL + pgvector |
| 部署 | Docker |
| 认证 | API Key |
| 前端框架 | Next.js 16 (App Router) |
| 前端 UI | shadcn/ui + Tailwind CSS |
| 前端语言 | TypeScript |
| 前端状态 | Zustand |

## 架构图

```
┌──────────────────────────┐
│   Web Client (Next.js)   │
│   shadcn/ui + Zustand    │
└──────────┬───────────────┘
           │ REST + SSE + API Key
           ▼
┌─────────────────────────────────┐
│        API Gateway (FastAPI)     │
│  认证 | 限流 | 日志 | 路由        │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────────────┐
│              Agent Core                  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ AgentLoop   │  │  LLMProvider     │  │
│  │ (核心循环)   │  │  (统一模型调用)   │  │
│  └──────┬──────┘  └──────────────────┘  │
│         │                                │
│  ┌──────┴──────┐  ┌──────────────────┐  │
│  │ EventBus    │  │ ApprovalManager  │  │
│  │ (事件总线)   │  │ (HITL 审批)      │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ SessionMgr  │  │ AgentBuilder     │  │
│  │ (会话管理)   │  │ (配置驱动组装)   │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐                         │
│  │ AgentRunner │                         │
│  │ (执行封装)   │                         │
│  └─────────────┘                         │
│                                          │
│  UnifiedToolRegistry                     │
│  (内置工具 │ Skill │ MCP)                 │
└──────────────┬──────────────────────────┘
               ▼
┌──────────────────┬──────────────┬──────────────┐
│ PostgreSQL       │ LLM Provider │ 智谱 AI      │
│ + pgvector       │ (Anthropic等)│ (Embedding)  │
│ - 会话/消息      │              │              │
│ - 配置           │              │              │
│ - 向量存储       │              │              │
└──────────────────┴──────────────┴──────────────┘
```

## 核心概念

| 概念 | 说明 | 示例 |
|------|------|------|
| **Tool** | 原子操作，通过 `@register_tool` 注册到 UnifiedToolRegistry | bash, read_file, http_request |
| **Skill** | Prompt 模板，通过上下文注入扩展能力 | code_review, doc_gen |
| **MCP** | 外部资源协议，支持延迟加载 | 文件系统, 数据库 |
| **Context** | 上下文管理，支持自动压缩（带缓存检查） | 摘要生成, 滑动窗口 |
| **AgentRunner** | Agent 执行封装，构建并运行 AgentLoop | 同步/流式执行、事件转换 |
| **Hook** | 生命周期钩子，在不修改主循环的前提下扩展行为 | RAG 注入、日志、安全过滤 |

### 上下文管理

Context Manager 负责对话历史的压缩，解决长对话的 token 限制问题。

**压缩流程**：
```
[msg1]...[msg40] → [SUMMARY] + [msg31]...[msg40]
                      │
              is_summarized=True (msg1-msg30)
```

**多次压缩支持**：
```
[SUMMARY_1]...[msg60] → [SUMMARY_2] + [msg51]...[msg60]
       │
       └── SUMMARY_1 也被标记为 is_summarized=True
```

**两种查询模式**：
- `get_context_for_llm()`：摘要 + 未压缩消息（精简版，用于 LLM）
- `get_messages_for_display()`：全部消息（完整版，用于前端）

**Message 模型扩展**：
```python
class Message:
    is_summarized: bool = False      # 是否已被压缩
    metadata: dict | None            # 摘要元数据（压缩的消息 ID 列表）
```

**配置参数**：
- `compression_threshold`: 触发压缩的消息数量阈值（默认 40）
- `keep_recent_count`: 保留的近期消息数量（默认 10）

**压缩检查缓存**：SessionManager 内置缓存机制，避免每次请求都查询 DB：
- 60 秒间隔检查 或 累积 5 条新消息后强制检查
- LRU 淘汰，最多缓存 1000 个 session
- 手动压缩后自动清除缓存

### MCP 集成

### Channel 集成

Channel 是连接 IM 平台（微信、飞书等）与 Agent 的消息通道。

**架构**（三层分离）：
```
PlatformProtocol（无状态协议层）← 从 channel config 按需创建
  ↕
PollerManager（轮询调度层）← 管理 asyncio.Task，cursor 持久化到 DB
  ↕
ChannelService（消息路由层）← 白名单、会话映射、调用 Agent
```

**核心组件**：
- `PlatformProtocol`：无状态 IM 协议抽象基类（纯 API 调用，无生命周期）
- `WeChatProtocol`：微信 ilink Bot 协议实现
- `WeChatAuth`：微信 QR 扫码登录（独立于协议）
- `ProtocolRegistry`：platform → Protocol 类映射，新增平台一行注册
- `PollerManager`：管理轮询任务，运行时状态（cursor、context_tokens）持久化到 `ChannelRuntime` 表
- `ChannelService`：纯消息路由 + IM↔Agent 会话映射

**会话映射**：IM 对话 ↔ Agent session 一对一绑定，保持对话上下文

**数据模型**：
- `Channel`：Channel 配置（平台、token、白名单等）
- `ChannelSession`：IM 会话与 Agent 会话的映射关系
- `ChannelRuntime`：运行时状态（轮询游标、context_tokens），重启可恢复

**新增平台**：只需创建 Protocol + Auth + API 路由 3 个文件，注册一行，不改旧代码。

### Skill 系统

**支持两种传输方式**：

| 传输类型 | 说明 | 使用场景 |
|---------|------|---------|
| **STDIO** | 子进程通信 | 本地 MCP Server |
| **HTTP/SSE** | HTTP + Server-Sent Events | 远程 MCP Server |

**配置存储**：

MCP Server 配置存储在数据库 `mcp_servers` 表中，通过 Web 管理界面（`/mcp`）进行 CRUD 操作。

首次启动时，`.mcp.json` 中的配置会自动迁移到数据库。环境变量支持 `${VAR}` 语法，在连接时解析。

**MCPManager API**：
- `load_configs_from_db(session)` — 从数据库加载配置
- `connect_server(name)` / `disconnect_server(name)` — 单个 Server 连接控制
- `get_server_details(name)` — 获取工具/资源/提示词
- `initialize()` / `shutdown()` — 批量连接管理

**配置示例**：

STDIO 方式：command + args + env（支持 `${VAR}` 环境变量替换）
HTTP 方式：url + headers（支持 `${VAR}` 环境变量替换）

**延迟加载（MCP Tool Search）**：
当 MCP 工具数量超过阈值（默认 10 个）时，自动启用延迟加载模式：

1. **初始化时**：只注册 `mcp_search` 元工具
2. **搜索阶段**：Claude 调用 `mcp_search` 查找匹配工具
3. **按需加载**：返回匹配工具列表，动态注册完整定义
4. **执行阶段**：Claude 使用注册的工具完成任务

**效果**：减少 85-95% 上下文占用

### Skill 系统

Skill 是基于 **Prompt 的元工具**，遵循 Claude Code 的设计规范：

```
Skill = SKILL.md (Prompt 模板) + 上下文注入 + 执行上下文修改
```

**核心特性**：
- **Prompt 模板**：不是可执行代码，而是指令模板
- **LLM 路由**：Claude 根据描述自主判断何时使用 skill
- **双消息注入**：元数据消息（用户可见）+ Skill prompt（隐藏）
- **执行上下文修改**：可限制工具权限、切换模型

**目录结构**：
```
skills/                      # 项目级 Skills（项目根目录）
├── code_review/
│   └── SKILL.md            # Skill 定义
└── doc_gen/
    └── SKILL.md

~/.claude-agent/skills/      # 用户级 Skills
```

**SKILL.md 结构**：
```markdown
---
name: skill_name
description: When to use this skill
allowed-tools: "read_file, list_dir"
version: "1.0.0"
---

# Skill Instructions
[详细的指令内容]
```

## 目录结构

```
claude-agent/
├── skills/                   # Skill 定义（项目根目录）
│   └── code_review/
│       └── SKILL.md
├── web/                      # 前端代码（Next.js）
│   ├── src/
│   │   ├── app/              # 页面路由（App Router）
│   │   │   ├── chat/         # 新对话页
│   │   │   ├── chat/[id]/    # 已有会话页
│   │   │   └── channels/     # Channel 管理页（独立布局）
│   │   ├── components/       # UI 组件
│   │   │   ├── ui/           # shadcn/ui 原子组件
│   │   │   ├── layout/       # 布局（Sidebar, AppShell）
│   │   │   ├── chat/         # 聊天组件（MessageList, ToolCallBlock 等）
│   │   │   └── channel/      # Channel 组件（ChannelStatus, QRLogin 等）
│   │   └── lib/              # 工具库
│   │       ├── api/          # API Client（fetch 封装 + 类型定义）
│   │       ├── sse/          # SSE 流解析器
│   │       ├── hooks/        # React Hooks（useChat, useSessions）
│   │       └── store/        # Zustand 状态管理
│   ├── next.config.ts
│   └── package.json
├── backend/                  # 后端代码
│   ├── __init__.py
│   ├── main.py               # FastAPI 入口
│   ├── config.py             # 配置管理
│   ├── core/                 # 核心逻辑（Agent 能力中心）
│   │   ├── __init__.py
│   │   ├── agent/            # Agent Core — 解耦后的核心模块
│   │   │   ├── __init__.py   # 公共 API 导出
│   │   │   ├── loop.py       # AgentLoop 核心循环
│   │   │   ├── runner.py     # AgentRunner 执行封装
│   │   │   ├── events.py     # EventBus + AgentEvent（支持有界队列）
│   │   │   ├── approval.py   # HITL 审批管理
│   │   │   ├── hooks.py      # AgentHook 生命周期钩子 + KnowledgeRetrievalHook
│   │   │   ├── session.py    # SessionManager 会话管理
│   │   │   ├── builder.py    # AgentBuilder 配置驱动组装
│   │   │   └── llm/          # LLM Provider 抽象
│   │   │       ├── base.py   # LLMProvider ABC + 数据类型
│   │   │       └── anthropic_provider.py
│   │   ├── agent_service.py  # Agent 服务（薄外观，委托给 AgentRunner）
│   │   ├── tools/            # 工具系统
│   │   │   ├── base.py       # @register_tool 装饰器（统一注册到 UnifiedToolRegistry）
│   │   │   ├── registry.py   # UnifiedToolRegistry 统一注册表
│   │   │   ├── bash.py       # Shell 命令工具
│   │   │   ├── file.py       # 文件操作工具
│   │   │   ├── http.py       # HTTP 请求工具
│   │   │   └── knowledge_search.py  # 知识库语义检索工具
│   │   ├── tool_executor.py  # 统一工具执行器
│   │   ├── tools/            # 工具模块（可扩展）
│   │   │   ├── __init__.py   # 工具注册入口
│   │   │   ├── base.py       # 基础类型和注册装饰器
│   │   │   ├── bash.py       # Shell 命令工具
│   │   │   ├── file.py       # 文件操作工具
│   │   │   └── http.py       # HTTP 请求工具
│   │   └── skills/           # Skill 系统实现
│   │       ├── __init__.py
│   │       ├── types.py      # 类型定义
│   │       ├── loader.py     # SKILL.md 加载器
│   │       └── registry.py   # Skill 注册中心
│   │   └── rag/              # RAG 文档处理
│   │       ├── __init__.py
│   │       ├── types.py      # 核心数据类型（ExtractedDocument, ChunkData）
│   │       ├── pipeline.py   # DocumentPipeline（提取→分块编排）
│   │       ├── embedding.py  # 智谱 Embedding 服务（异步批量向量化）
│   │       ├── vector_store.py # pgvector 向量存储与语义检索
│   │       ├── extractors/   # 文档提取器
│   │       │   ├── base.py   # BaseExtractor ABC
│   │       │   ├── markdown.py
│   │       │   ├── pdf.py    # PyMuPDF 结构化提取（字体分析 + 表格检测）
│   │       │   ├── plaintext.py  # txt/csv/json
│   │       │   ├── docx.py   # python-docx
│   │       │   ├── html.py   # BeautifulSoup
│   │       │   └── registry.py  # 扩展名→提取器映射
│   │       ├── chunkers/     # 文档分块器
│   │       │   ├── base.py   # BaseChunker ABC
│   │       │   ├── markdown_chunker.py  # Markdown 标题分块
│   │       │   ├── pdf_chunker.py       # PDF 结构感知分块（标题 + 页码）
│   │       │   ├── recursive_chunker.py # 递归字符分块（中文标点）
│   │       │   └── factory.py           # 分块器工厂
│   │       └── crawler/      # URL 爬取
│   │           └── web_crawler.py  # 异步网页爬虫
│   │   └── context/          # 上下文管理
│   │       ├── __init__.py
│   │       └── manager.py    # 上下文压缩管理器
│   │       └── registry.py   # Skill 注册中心
│   │   └── mcp/              # MCP 集成
│   │       ├── __init__.py
│   │       ├── types.py      # MCP 类型定义（含 BaseTransport、JSONRPCMessage）
│   │       ├── client.py     # MCP Client
│   │       ├── manager.py    # MCP Server 管理器
│   │       └── transport/    # 传输层
│   │           ├── stdio.py  # STDIO 传输
│   │           └── http.py   # HTTP/SSE 传输
│   │   └── channel/          # IM Channel 集成
│   │       ├── __init__.py   # 协议注册入口
│   │       ├── protocol.py   # PlatformProtocol 抽象 + PlatformMessage/PollResult
│   │       ├── registry.py   # ProtocolRegistry（platform → Protocol 映射）
│   │       ├── poller.py     # PollerManager（轮询任务管理 + cursor 持久化）
│   │       ├── service.py    # ChannelService（消息路由 + 会话映射）
│   │       ├── wechat_protocol.py  # 微信 ilink Bot 无状态协议
│   │       └── wechat_auth.py      # 微信 QR 扫码登录
│   ├── api/                  # API 层
│   │   ├── __init__.py       # 路由注册
│   │   ├── chat.py           # 对话接口
│   │   ├── sessions.py       # 会话管理
│   │   ├── skills.py         # Skills 接口
│   │   ├── channel.py        # Channel 通用 CRUD + 启停
│   │   └── channel_wechat.py # 微信特定（QR 登录）
│   │   └── schemas/          # Pydantic 模型（请求/响应）
│   │       ├── __init__.py
│   │       ├── chat.py
│   │       └── session.py
│   ├── db/                   # 数据库层
│   │   ├── __init__.py
│   │   ├── database.py       # 连接管理
│   │   └── models/           # SQLAlchemy ORM 模型
│   │       ├── __init__.py
│   │       ├── session.py
│   │       ├── channel.py    # Channel + ChannelSession + ChannelRuntime 模型
│   │       └── knowledge_base.py  # KnowledgeBase + Document(embedding_status) + DocumentChunk
│   └── middleware/           # 中间件
│       ├── __init__.py
│       └── auth.py           # API Key 认证
├── docs/                     # 文档
├── data/                     # 数据目录（gitignore）
├── tests/                    # 测试
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

**分层说明**：
- `api/schemas/`: Pydantic 模型，API 请求/响应验证
- `db/models/`: SQLAlchemy ORM 模型，数据库表映射

## API 设计

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/chat` | POST | 对话（非流式） |
| `/api/chat/stream` | POST | 对话（流式 SSE） |
| `/api/sessions` | GET/POST | 会话管理 |
| `/api/tools` | GET | 可用工具列表（用于 Agent 配置） |
| `/api/skills` | GET | 技能列表 |
| `/api/agent-configs` | GET/POST | Agent 配置 CRUD |
| `/api/agent-configs/{id}` | GET/PUT/DELETE | Agent 配置详情/更新/删除 |
| `/api/channels` | POST/GET | Channel 管理 |
| `/api/channels/{id}/start` | POST | 启动 Channel |
| `/api/channels/{id}/stop` | POST | 停止 Channel |
| `/api/channels/wechat/{id}/qrcode` | POST | 微信登录二维码 |
| `/api/channels/wechat/{id}/status` | GET | 微信登录状态 |
| `/api/knowledge-bases` | GET/POST | 知识库管理 |
| `/api/knowledge-bases/{id}` | GET/PUT/DELETE | 知识库详情 |
| `/api/knowledge-bases/{id}/documents` | GET | 文档列表 |
| `/api/knowledge-bases/{id}/documents/upload` | POST | 上传文件 |
| `/api/knowledge-bases/{id}/documents/url` | POST | URL 导入 |
| `/api/knowledge-bases/{id}/documents/text` | POST | 文本导入 |
| `/api/knowledge-bases/{id}/documents/{doc_id}/chunks` | GET | 文档分块列表 |
| `/api/knowledge-bases/search` | POST | 跨知识库语义搜索 |

### Agent RAG（Hybrid）流程

Agent 绑定知识库后，采用 Hybrid RAG 策略，通过 **KnowledgeRetrievalHook** 实现：

1. **Pre-Retrieval（Hook 注入）**：`KnowledgeRetrievalHook` 在首轮 LLM 调用前，自动从绑定知识库检索 top-3 相关片段，注入到 **user message**（非 system prompt），保证 prompt cache 命中
2. **Tool-Augmented**：保留 `knowledge_search` 工具，LLM 可主动深入检索
3. Agent 配置通过 `knowledge_base_ids` 字段绑定知识库
4. `AgentBuilder` 根据 `knowledge_base_ids` 自动创建 `KnowledgeRetrievalHook`

### Hook 机制

AgentLoop 支持 4 个生命周期钩子点，通过 `AgentHook` Protocol 实现：

| 钩子 | 时机 | 典型场景 |
|------|------|---------|
| `on_before_llm` | LLM 调用前，可修改 messages / system_prompt | RAG 注入、上下文压缩 |
| `on_after_llm` | LLM 响应后 | 响应过滤、日志记录 |
| `on_before_tool` | 工具执行前，可修改输入或拒绝（返回 None） | 权限控制、输入校验 |
| `on_after_tool` | 工具执行后，可修改输出 | 输出脱敏、日志记录 |

**Hook 注册方式**：`AgentBuilder._build_hooks()` 根据 `AgentConfig` 自动创建 Hook 列表，传入 `AgentLoop`。

**内置 Hook**：
- `KnowledgeRetrievalHook`：Pre-Retrieval RAG，仅在首轮迭代执行，检索结果注入 user message

**扩展方式**：实现 `AgentHook` Protocol，在 `_build_hooks()` 中注册。

### 请求示例

```json
POST /api/chat
{
  "message": "分析项目代码",
  "session_id": "xxx",         // 可选
  "agent_config_id": "yyy"     // 可选，创建新会话时绑定 Agent 配置
}
```

### 响应示例

```json
{
  "session_id": "xxx",
  "message": "好的，让我分析...",
  "tool_calls": [
    {"name": "bash", "input": {"cmd": "ls"}, "output": "..."}
  ]
}
```
