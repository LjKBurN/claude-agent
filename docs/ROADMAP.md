# 开发计划

## 阶段概览

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5
 基础架构      核心Agent     流式+工具      Skill系统      MCP集成       生产化
  1-2天        3-5天        3-5天         3-5天         3-5天        3-5天
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
