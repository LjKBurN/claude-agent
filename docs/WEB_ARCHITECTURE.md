# Web 客户端技术架构

## 技术栈

| 层级 | 选型 | 版本 |
|------|------|------|
| 框架 | Next.js (App Router) | 16.x |
| 语言 | TypeScript | 5.x |
| UI 组件库 | shadcn/ui | 4.x |
| 样式 | Tailwind CSS | 4.x |
| 状态管理 | Zustand | 5.x |
| 数据请求 | SWR | 2.x |
| 主题切换 | next-themes | 0.x |
| 图标 | lucide-react | - |
| Markdown | react-markdown + remark-gfm | 待集成 |
| 代码高亮 | shiki | 待集成 |

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                       Next.js App Router                        │
│                                                                 │
│  ┌──────────┐    ┌──────────────────────────────────────────┐  │
│  │  Pages    │    │            Components                     │  │
│  │          │    │                                          │  │
│  │ /chat    │───▶│  AppShell                                │  │
│  │ /chat/[id]│   │  ├── Sidebar                             │  │
│  │          │    │  │   ├── SidebarSessions (会话列表)       │  │
│  │          │    │  │   ├── SkillsPanel (技能面板)           │  │
│  │          │    │  │   └── ThemeToggle                      │  │
│  │          │    │  └── ChatView (聊天主区域)                │  │
│  │          │    │      ├── MessageList                      │  │
│  │          │    │      │   ├── MessageItem                  │  │
│  │          │    │      │   ├── StreamingText                │  │
│  │          │    │      │   └── ToolCallBlock                │  │
│  │          │    │      ├── MessageInput                     │  │
│  │          │    │      └── EmptyState                       │  │
│  └──────────┘    └──────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     Data Layer                            │  │
│  │                                                          │  │
│  │  Hooks                 Stores              API Client    │  │
│  │  ├── useChat()    ◀──  chat-store    ◀──   client.ts     │  │
│  │  ├── useSessions() ◀─  (SWR cache)   ◀──   sessions.ts  │  │
│  │  └── useScrollAnchor()                                   │  │
│  │                                            SSE Parser    │  │
│  │                                            parser.ts      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │                              │
        │ REST (fetch)                 │ SSE (ReadableStream)
        ▼                              ▼
┌─────────────────────────────────────────────┐
│          Backend (FastAPI :8000)             │
│  /api/chat  /api/sessions  /api/skills       │
└─────────────────────────────────────────────┘
```

## 目录结构

```
web/
├── src/
│   ├── app/                        # 页面路由 (App Router)
│   │   ├── layout.tsx              # 根布局：ThemeProvider + TooltipProvider + Toaster
│   │   ├── page.tsx                # 首页：redirect → /chat
│   │   ├── globals.css             # Tailwind + shadcn/ui CSS 变量 (dark/light)
│   │   └── chat/
│   │       ├── layout.tsx          # Chat 布局：AppShell 包装
│   │       ├── page.tsx            # 新对话页
│   │       └── [sessionId]/
│   │           └── page.tsx        # 已有会话页（加载历史消息）
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn/ui 原子组件 (自动生成)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── sheet.tsx           # 移动端侧边栏
│   │   │   ├── scroll-area.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── skeleton.tsx        # 加载占位
│   │   │   ├── separator.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── avatar.tsx
│   │   │   └── sonner.tsx          # Toast 通知
│   │   │
│   │   ├── layout/                 # 布局组件
│   │   │   ├── app-shell.tsx       # 应用外壳：桌面 Sidebar + 移动 Sheet
│   │   │   ├── sidebar.tsx         # 侧边栏：新对话按钮 + 会话列表 + Skills
│   │   │   ├── sidebar-sessions.tsx # 会话列表：加载、切换、删除
│   │   │   └── theme-toggle.tsx    # Dark/Light 切换按钮
│   │   │
│   │   └── chat/                   # 聊天功能组件
│   │       ├── chat-view.tsx       # 主编排组件：组合 MessageList + MessageInput
│   │       ├── message-list.tsx    # 消息列表：自动滚动到底部
│   │       ├── message-item.tsx    # 单条消息：头像 + 内容 + 工具调用
│   │       ├── message-input.tsx   # 输入框：自动扩高、Enter 发送、停止按钮
│   │       ├── streaming-text.tsx  # 流式文本：闪烁光标
│   │       ├── tool-call-block.tsx # 工具调用卡片：可折叠、状态图标
│   │       ├── code-block.tsx      # 代码块：复制按钮
│   │       ├── skills-panel.tsx    # Skills 列表面板
│   │       └── empty-state.tsx     # 空状态占位
│   │
│   ├── lib/
│   │   ├── api/                    # API 客户端层
│   │   │   ├── types.ts            # TypeScript 类型（与后端 Schema 对齐）
│   │   │   ├── client.ts           # fetch 封装：Base URL + API Key + 错误处理
│   │   │   ├── chat.ts             # POST /api/chat + POST /api/chat/stream
│   │   │   ├── sessions.ts         # GET /api/sessions, GET/DELETE /api/sessions/:id
│   │   │   └── skills.ts           # GET /api/skills, POST /api/skills/reload
│   │   │
│   │   ├── sse/
│   │   │   └── parser.ts           # SSE 流解析器（POST ReadableStream）
│   │   │
│   │   ├── hooks/                  # React Hooks
│   │   │   ├── use-chat.ts         # 聊天核心 hook：发送、SSE、中止
│   │   │   ├── use-sessions.ts     # 会话列表 hook：SWR 缓存
│   │   │   └── use-scroll-anchor.ts # 自动滚动 hook
│   │   │
│   │   ├── store/                  # Zustand 状态管理
│   │   │   ├── chat-store.ts       # 聊天状态：消息、流式文本、工具调用
│   │   │   └── ui-store.ts         # UI 状态：Sidebar 开关
│   │   │
│   │   └── utils.ts                # 工具函数 (cn 等)
│   │
│   └── types/                      # 预留：前端业务类型扩展
│
├── .env.local                      # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_API_KEY
├── .env.example                    # 环境变量模板
├── next.config.ts                  # API proxy rewrite (/api/* → :8000/api/*)
├── components.json                 # shadcn/ui 配置
├── tailwind.config.ts              # Tailwind 配置
├── package.json
└── tsconfig.json
```

## 核心模块设计

### 1. API Client 层

**Base Client** (`lib/api/client.ts`)：
- 读取 `NEXT_PUBLIC_API_URL`（默认 `http://localhost:8000`）
- `NEXT_PUBLIC_API_KEY` 非空时注入 `X-API-Key` Header
- `request<T>()` 通用方法：处理 JSON 序列化、HTTP 错误解析
- `requestStream()` 流式方法：返回 `ReadableStream<Uint8Array>`

**类型定义** (`lib/api/types.ts`) 与后端 Pydantic Schema 一一对应：

```typescript
// 后端 backend/api/schemas/chat.py
interface ChatRequest { message: string; session_id?: string | null }
interface ChatResponse { session_id: string; message: string; tool_calls: ToolCall[] }
interface ToolCall { name: string; input: Record<string, unknown>; output: string }

// 后端 backend/api/schemas/session.py
interface SessionInfo { id: string; created_at: string; updated_at: string; message_count: number }
interface MessageInfo { id: number; role: string; content: string; created_at: string }
```

### 2. SSE Parser

后端流式端点 `POST /api/chat/stream` 返回格式：

```
event: session_id
data: {"session_id": "xxx"}

event: text
data: {"content": "你"}

event: tool_start
data: {"name": "bash"}

event: tool_end
data: {"name": "bash", "output": "file1.txt\nfile2.txt"}

event: skill_load
data: {"name": "code_analyzer", "message": "loading..."}

event: mcp_tools_loaded
data: {"count": 3, "tools": ["tool_a", "tool_b", "tool_c"]}

event: done
data: {"tool_calls": [...]}
```

因后端使用 POST 请求，不能用浏览器原生 `EventSource`（仅支持 GET），需用 `fetch` + `ReadableStream` 手动解析。

解析器核心逻辑：
1. `reader.read()` 循环读取 chunk
2. `TextDecoder` 解码为字符串
3. 以 `\n\n` 分割 SSE 事件
4. 解析 `event:` 和 `data:` 行
5. `JSON.parse` 解析 data，按 event type 返回类型化对象

### 3. 状态管理

**chat-store** (`lib/store/chat-store.ts`)：

| 状态字段 | 类型 | 说明 |
|---------|------|------|
| `sessionId` | `string \| null` | 当前会话 ID |
| `messages` | `DisplayMessage[]` | 已完成的消息列表 |
| `isStreaming` | `boolean` | 是否正在接收 SSE 流 |
| `streamingText` | `string` | 当前流的累积文本 |
| `streamingToolCalls` | `ToolCall[]` | 当前流已完成的工具调用 |
| `streamingToolName` | `string \| null` | 正在执行的工具名称 |
| `error` | `string \| null` | 最近一次错误 |

**状态流转**：

```
[空闲] ──send()──▶ [流式中] ──done──▶ [空闲]
                     │                  ▲
                     │  text/tool事件    │
                     └──▶ 更新 store ────┘
                     │
                     └──abort()──▶ [空闲] (保留已有内容)
```

**选择 Zustand 的原因**：
- SSE 流每秒产生多次 `text` 事件更新 `streamingText`，Zustand 的 selector 机制允许组件只订阅需要的状态片段，避免无关组件重渲染
- 无 Provider 包裹，可在 React 组件外使用
- API 简洁，无 boilerplate

### 4. Hooks

**useChat** (`lib/hooks/use-chat.ts`)：
- 封装完整的聊天生命周期：发送消息 → 建立 SSE 连接 → 处理事件 → 更新 store → 完成或中止
- 内部持有 `AbortController` 引用，支持用户手动停止流
- 通过 `useChatStore` selector 暴露状态，组件按需订阅

**useSessions** (`lib/hooks/use-sessions.ts`)：
- 基于 SWR 的数据请求缓存
- 自动 revalidate on focus（切换浏览器标签回来时刷新）
- 提供 `remove()` 方法删除会话后自动刷新列表

### 5. 组件体系

**AppShell**：响应式外壳
- 桌面端（`md:`）：固定 Sidebar + 主内容区
- 移动端：隐藏 Sidebar，通过 Sheet (Drawer) 打开

**ChatView**：聊天主编排
- 组合 `MessageList` + `MessageInput`
- 错误条展示

**MessageList**：消息渲染
- 自动滚动到底部（监听 messages/streamingText 变化）
- 流式状态区：显示 `StreamingText`（闪烁光标）+ 正在执行的工具（loading spinner）

**ToolCallBlock**：工具调用可视化
- 可折叠卡片，header 显示工具图标 + 名称 + 状态
- 根据工具名称自动匹配图标（Terminal/FileText/Globe/Wrench/Puzzle）
- Input/Output 区域独立展示，长内容默认折叠
- 正在执行时展开并显示 spinner，完成后折叠并显示 checkmark

## 路由设计

| 路由 | 页面文件 | 说明 |
|------|---------|------|
| `/` | `app/page.tsx` | 重定向到 `/chat` |
| `/chat` | `app/chat/page.tsx` | 新建对话（reset store） |
| `/chat/[sessionId]` | `app/chat/[sessionId]/page.tsx` | 加载已有会话消息 |

## API 代理

`next.config.ts` 配置了 rewrite 规则：

```typescript
rewrites: [
  { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }
]
```

- 开发环境：前端 `localhost:3000` 通过代理访问后端 `localhost:8000`，避免跨域
- 生产环境：可修改 `NEXT_PUBLIC_API_URL` 指向后端实际地址

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEXT_PUBLIC_API_URL` | 后端 API 地址 | `http://localhost:8000` |
| `NEXT_PUBLIC_API_KEY` | API 认证密钥 | 空（开发模式跳过认证） |

## 开发命令

```bash
cd web

# 安装依赖
npm install

# 开发服务器
npm run dev

# 构建生产版本
npm run build

# 运行生产版本
npm start

# 添加 shadcn/ui 组件
npx shadcn@latest add [component-name]
```
