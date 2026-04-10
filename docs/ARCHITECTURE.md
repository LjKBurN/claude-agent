# 技术架构

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端语言 | Python 3.10+ |
| 后端框架 | FastAPI |
| Agent | LangChain + LangGraph |
| 数据库 | SQLite → PostgreSQL |
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
┌─────────────────────────────────┐
│          Agent Core              │
│  ┌───────────────────────────┐  │
│  │    LangGraph Workflow     │  │
│  │  Router → Agent → Output  │  │
│  └───────────────────────────┘  │
│  Tools │ Skills │ MCP           │
└──────────────┬──────────────────┘
               ▼
┌──────────────────┬──────────────┐
│ SQLite (存储)    │ Anthropic    │
│ - 会话/消息      │ (LLM)        │
│ - 配置           │              │
└──────────────────┴──────────────┘
```

## 核心概念

| 概念 | 说明 | 示例 |
|------|------|------|
| **Tool** | 原子操作 | bash, read_file, http_request |
| **Skill** | Prompt 模板，通过上下文注入扩展能力 | code_review, doc_gen |
| **MCP** | 外部资源协议，支持延迟加载 | 文件系统, 数据库 |
| **Context** | 上下文管理，支持自动压缩 | 摘要生成, 滑动窗口 |

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

### MCP 集成

### Channel 集成

Channel 是连接 IM 平台（微信、飞书等）与 Agent 的消息通道。

**架构**：
```
IM 平台 → ChannelAdapter → ChannelService → AgentService.chat() → Adapter.send_message() → IM 平台
```

**核心组件**：
- `ChannelAdapter`：IM 平台适配器抽象基类
- `WeChatAdapter`：微信 ilink Bot 实现（长轮询 + context_token 管理）
- `ChannelService`：管理生命周期、消息路由、会话映射

**会话映射**：IM 对话 ↔ Agent session 一对一绑定，保持对话上下文

**数据模型**：
- `Channel`：Channel 配置（平台、token、白名单等）
- `ChannelSession`：IM 会话与 Agent 会话的映射关系

### MCP 集成

MCP (Model Context Protocol) 是连接外部资源的标准协议。

**支持两种传输方式**：

| 传输类型 | 说明 | 使用场景 |
|---------|------|---------|
| **STDIO** | 子进程通信 | 本地 MCP Server |
| **HTTP/SSE** | HTTP + Server-Sent Events | 远程 MCP Server |

**配置格式**（`.mcp.json`，与 Claude Code 兼容）：

STDIO 方式：
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/path"],
      "env": {"KEY": "${ENV_VAR}"}
    }
  }
}
```

HTTP 方式：
```json
{
  "mcpServers": {
    "remote-server": {
      "url": "http://localhost:8080",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  }
}
```

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
│   │   │   └── chat/[id]/    # 已有会话页
│   │   ├── components/       # UI 组件
│   │   │   ├── ui/           # shadcn/ui 原子组件
│   │   │   ├── layout/       # 布局（Sidebar, AppShell）
│   │   │   └── chat/         # 聊天组件（MessageList, ToolCallBlock 等）
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
│   │   ├── agent_service.py  # Agent 服务
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
│   │       ├── __init__.py
│   │       ├── types.py      # 共享类型
│   │       ├── base.py       # ChannelAdapter 抽象基类
│   │       ├── service.py    # ChannelService 核心逻辑
│   │       └── wechat.py     # 微信 ilink Bot Adapter
│   ├── api/                  # API 层
│   │   ├── __init__.py       # 路由注册
│   │   ├── chat.py           # 对话接口
│   │   ├── sessions.py       # 会话管理
│   │   ├── skills.py         # Skills 接口
│   │   └── channel.py        # Channel 管理 + 微信登录
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
│   │       └── channel.py    # Channel + ChannelSession 模型
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
| `/api/tools` | GET | 工具列表 |
| `/api/skills` | GET | 技能列表 |
| `/api/channels` | POST/GET | Channel 管理 |
| `/api/channels/{id}/start` | POST | 启动 Channel |
| `/api/channels/{id}/stop` | POST | 停止 Channel |
| `/api/channels/wechat/{id}/qrcode` | POST | 微信登录二维码 |
| `/api/channels/wechat/{id}/status` | GET | 微信登录状态 |

### 请求示例

```json
POST /api/chat
{
  "message": "分析项目代码",
  "session_id": "xxx",    // 可选
  "skill": "code_review", // 可选
  "stream": false         // 可选
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
