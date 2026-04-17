# 开发计划

## 阶段概览

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5 ──▶ Phase 6 ──▶ Phase 7 ──▶ Phase 8
 基础架构      核心Agent     流式+工具      Skill系统      MCP集成       生产化       Web客户端     Channel前端    Agent Core解耦
  1-2天        3-5天        3-5天         3-5天         3-5天        3-5天        3-5天        3-5天          ✅
```

**总计**：约 4-5 周

---

## Phase 0: 项目基础（1-2 天）✅

**目标**：搭建可运行的 API 服务骨架

**任务**：
- [x] 初始化 FastAPI 项目结构
- [x] 实现 `/health` 健康检查
- [x] 配置环境变量（pydantic-settings）
- [x] API Key 认证中间件
- [x] Docker 配置

**验收**：
```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Phase 1: 核心 Agent（3-5 天）✅

**目标**：实现基础对话能力

**任务**：
- [x] `/api/chat` 接口（非流式）
- [x] 集成 LangChain + Anthropic
- [x] 基础 Tool：bash, read_file, write_file
- [x] SQLite 存储（会话+消息）
- [x] 会话管理 API

**验收**：
```bash
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "列出当前目录文件"}'
# 返回带工具调用的响应
```

---

## Phase 2: 流式输出 & 工具扩展（3-5 天）✅

**目标**：提升用户体验

**任务**：
- [x] SSE 流式输出 `/api/chat/stream`
- [x] 新增 Tool：http_request, edit_file, list_dir
- [x] Tool 动态注册机制
- [x] Swagger 文档（FastAPI 内置）

**验收**：流式输出实时显示

---

## Phase 3: Skill 系统（3-5 天）🔄

**目标**：可复用技能模块

**任务**：
- [x] Skill 抽象层设计（基于 Claude Code 规范）
- [x] SKILL.md 加载器
- [x] Skill 注册中心
- [x] 实现 `code_review` Skill
- [x] `/api/skills` 接口
- [x] Agent 集成 Skill meta-tool
- [ ] 更多内置 Skills（doc_gen, test_gen）
- [ ] Skill 权限控制（allowed-tools）

**验收**：
```bash
# 列出可用 skills
curl http://localhost:8000/api/skills

# 对话时 Claude 自动判断是否需要使用 skill
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "帮我审查 backend/tools.py 的代码"}'
```

---

## Phase 4: MCP 集成（3-5 天）🔄

**目标**：接入外部资源协议

**任务**：
- [x] MCP 类型定义（Tool, Resource, Prompt）
- [x] STDIO Transport 实现
- [x] MCP Client 实现
- [x] MCP Manager（多 Server 管理）
- [x] Tool 适配器（转换为 Anthropic 格式）
- [x] AgentService 集成
- [x] 配置文件支持（mcp_servers.yaml）
- [ ] HTTP Transport 实现
- [ ] 动态加载/卸载 MCP Server
- [ ] MCP 资源和 Prompt 支持

**验收**：
```bash
# 配置 MCP Server
cat mcp_servers.yaml

# 调用时自动使用 MCP 工具
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "使用 filesystem 工具读取 README.md"}'
```

---

## Phase 5: 生产化（3-5 天）

**目标**：生产环境就绪

**任务**：
- [ ] 限流中间件
- [ ] 结构化日志
- [ ] 错误处理
- [ ] 单元测试
- [ ] 部署文档

---

## Phase 6: Web 客户端（3-5 天）✅

**目标**：提供 Web 端交互界面

**技术选型**：Next.js 16 + shadcn/ui + Zustand + TypeScript

**任务**：
- [x] Next.js 项目脚手架 + shadcn/ui 初始化
- [x] API Client 层（fetch 封装、类型定义、SSE 解析）
- [x] Zustand 状态管理（chat-store、ui-store）
- [x] 聊天 UI（消息列表、流式文本、输入框、停止按钮）
- [x] 工具调用可视化（可折叠卡片、状态图标）
- [x] Sidebar 会话管理（列表、切换、删除）
- [x] Skills 面板（列表展示、重新加载）
- [x] Dark/Light 主题切换
- [x] 响应式布局（移动端 Sheet 侧边栏）
- [ ] Markdown 渲染 + 代码高亮（react-markdown + shiki）
- [ ] Docker 集成（docker-compose 添加 web 服务）

---

## Phase 7: Channel 前端集成（3-5 天）🔄

**目标**：Web 端管理 Channel，实现微信扫码登录、启停控制、关联会话查看

**任务**：
- [x] Channel API 层（types.ts + channels.ts）
- [x] SWR Hook（use-channels.ts）
- [x] Channel 列表页（/channels，独立布局）
- [x] Channel 详情页（/channels/[channelId]，启停 + 登录 + 白名单 + 会话）
- [x] 微信扫码登录组件（QR 码展示 + 状态轮询）
- [x] 白名单管理组件
- [x] 关联会话列表组件
- [x] 侧边栏入口（Channel 管理链接）

**验收**：
```bash
# 启动后端
python -m backend

# 启动前端
cd web && npm run dev

# 访问 http://localhost:3000
# - 新建对话、发送消息、SSE 流式响应
# - 工具调用过程可视化
# - 切换/删除会话
# - Dark/Light 主题切换
```

---

## Phase 8: Agent Core 解耦 ✅

**目标**：参照 Pi 的 "LLM + Tools + Loop" 极简架构，将 AgentService（937行）拆分为可插拔的 Agent Core，支持 Web 端通过配置拼装自定义 Agent。

**完成的工作**：

### 核心抽象

| 模块 | 文件 | 职责 |
|------|------|------|
| **LLMProvider** | `agent/llm/base.py` | 统一 LLM 调用接口（含 Anthropic 实现） |
| **AgentLoop** | `agent/loop.py` | 核心工具调用循环，不了解 SSE/DB/Channel |
| **EventBus** | `agent/events.py` | 事件总线，解耦事件生产与消费 |
| **ApprovalManager** | `agent/approval.py` | HITL 审批管理 |
| **SessionManager** | `agent/session.py` | 会话管理门面（DB CRUD + 上下文压缩） |
| **UnifiedToolRegistry** | `tools/registry.py` | 统一内置/Skill/MCP 工具注册表 |
| **AgentBuilder** | `agent/builder.py` | 配置驱动的 Agent 组装 |

### 关键成果

- **AgentService 从 937 行瘦身到 488 行**（薄外观，委托给 AgentLoop + SessionManager）
- **零业务逻辑在 AgentLoop 中**：不了解 SSE、DB、Channel，只做 LLM → 工具 → 循环
- **AgentConfig → AgentLoop**：Web 端可通过 JSON 配置选择性启用工具
- **EventBus 解耦**：核心循环通过事件通信，SSE/WebSocket/日志是不同的消费者
- **向后兼容**：所有现有 API 端点行为不变

### 新增文件

```
backend/core/agent/
├── __init__.py          # 公共 API 导出
├── loop.py              # AgentLoop 核心循环
├── events.py            # EventBus + AgentEvent
├── approval.py          # HITL 审批管理
├── session.py           # SessionManager 会话管理
├── builder.py           # AgentBuilder 配置驱动组装
└── llm/
    ├── __init__.py
    ├── base.py           # LLMProvider ABC
    └── anthropic_provider.py
backend/core/tools/
└── registry.py          # UnifiedToolRegistry
```

**验收**：
```python
# 通过配置创建自定义 Agent
from backend.core.agent import AgentBuilder, AgentConfig

config = AgentConfig(
    name="code-assistant",
    builtin_tools=["bash", "read_file", "write_file"],
    include_skills=False,
    include_mcp=False,
)
loop = AgentBuilder(config).build(api_key="...")
result = await loop.run(messages, system_prompt)
```

---

## Phase 9: AgentBuilder 集成 ✅

**目标**：将 AgentBuilder 接入完整链路 — DB 持久化、API CRUD、Web 管理页面、聊天流程集成

### 后端变更

| 变更 | 文件 | 说明 |
|------|------|------|
| 新增 DB 模型 | `db/models/agent_config.py` | AgentConfigModel（name, tools, model, skills/mcp 开关等） |
| 修改 Session | `db/models/session.py` | 新增 `agent_config_id` FK，会话绑定 Agent |
| 新增 CRUD API | `api/agent_configs.py` | GET/POST/PUT/DELETE `/api/agent-configs` |
| 新增工具列表 API | `api/tools.py` | GET `/api/tools` — 返回可用工具列表（前端 Agent 表单用） |
| 修改 ChatRequest | `api/schemas/chat.py` | 新增 `agent_config_id` 字段 |
| 修改 SessionInfo | `api/schemas/session.py` | 新增 `agent_config_id` + `agent_name` |
| 修改 Sessions API | `api/sessions.py` | 支持 `?agent_config_id=xxx` 过滤 |
| 修改 AgentService | `core/agent_service.py` | `_resolve_runner()` 从 DB 加载 config → AgentBuilder 构建 |
| 修改 Chat API | `api/chat.py` | 传递 `agent_config_id` 到 AgentService |

### 前端变更

| 变更 | 文件 | 说明 |
|------|------|------|
| 新增类型 | `lib/api/types.ts` | AgentConfigInfo, ToolInfo, CreateAgentConfigRequest 等 |
| 新增 API | `lib/api/agent-configs.ts` | listAgentConfigs, create, update, delete |
| 新增 API | `lib/api/tools.ts` | listTools |
| 新增 Hook | `lib/hooks/use-agent-configs.ts` | useAgentConfigs, useAgentConfig (SWR) |
| 修改 Store | `lib/store/chat-store.ts` | 新增 currentAgentId |
| 修改 useChat | `lib/hooks/use-chat.ts` | 传递 agent_config_id 到 sendMessageStream |
| 新增页面 | `app/agents/page.tsx` | Agent 列表页（卡片展示 + 删除） |
| 新增页面 | `app/agents/new/page.tsx` | Agent 创建页 |
| 新增页面 | `app/agents/[id]/page.tsx` | Agent 编辑页 |
| 新增组件 | `components/agent/agent-form.tsx` | 完整配置表单（模型/工具/Skills/MCP/Prompt） |
| 新增组件 | `components/layout/agent-selector.tsx` | 侧边栏 Agent 下拉选择器 |
| 修改侧边栏 | `components/layout/sidebar.tsx` | 集成 AgentSelector |
| 修改聊天 | `components/chat/chat-view.tsx` | 显示当前 Agent 标识 |

### 数据流

```
用户在侧边栏选择 Agent → currentAgentId (Zustand)
  → 点击"新对话" → /chat 页面
  → 发送消息 → sendMessageStream({ message, agent_config_id })
  → 后端创建 Session，绑定 agent_config_id
  → _resolve_runner(db, config_id) → DB 加载 → AgentBuilder(config).build()
  → 自定义 AgentLoop 执行对话
```

**验收**：
```bash
# 创建自定义 Agent
curl -X POST /api/agent-configs \
  -d '{"name":"Code Reviewer","builtin_tools":["bash","read_file"]}'

# 列出工具
curl /api/tools

# 用 Agent 聊天
curl -X POST /api/chat/stream \
  -d '{"message":"hello","agent_config_id":"xxx"}'

# Session 显示关联的 Agent
curl /api/sessions
```
