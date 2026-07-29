# OpenClaw Ultimate

本地优先、模块化、可扩展的 AI Agent 平台。

OpenClaw Ultimate 当前可以连接 Ollama，通过异步 Agent Runtime
完成多轮对话、工具调用、持久化会话、规划执行、失败恢复、知识检索，
并与本机 OpenClaw、Browser 和 ComfyUI 双向协作。

## 当前能力

- OpenAI-Compatible 聊天与 Embedding 适配器
- Ollama 本地模型接入
- 多步骤 Agent 与同步/异步工具调用
- SQLite 持久化会话
- Token 预算与滚动会话摘要
- 基于向量检索的长期记忆
- 受工作区边界保护的文件列表、读取和文本搜索
- 默认关闭的白名单命令执行
- 带 DAG 校验和 SQLite 持久化的任务 Planner
- 按依赖顺序执行步骤并持久化结果的 Executor
- 失败分类、Reflection、有限重试和候选计划修订
- 与本机 OpenClaw Gateway 的双向集成
- 基于实际 Ollama 库存与 8GB 显存预算的模型路由
- 确定性的 OpenClaw Browser 网页读取
- 复用 OpenClaw 现有 ComfyUI 工作流的本地生图
- 白名单 MCP stdio 客户端（默认关闭）
- 16 份本地文档、667 个文本块的增量知识索引
- 带文件路径和行号的混合 RAG 检索
- 仅监听回环地址的本地 JSON API
- 统一状态、启动、停止和全量验证脚本
- 环境、模型和工作区健康检查

## 快速开始

```powershell
.\bootstrap.ps1
uv run ocu doctor
uv run ocu status
uv run ocu chat
```

单次对话：

```powershell
uv run ocu chat "请介绍这个项目"
```

恢复持久化会话：

```powershell
uv run ocu session list
uv run ocu chat --session <SESSION_ID>
```

管理长期记忆：

```powershell
uv run ocu memory remember "用户喜欢航空和人工智能"
uv run ocu memory search "我的兴趣"
uv run ocu memory list
```

创建和查看任务计划：

```powershell
uv run ocu plan create "检查仓库、运行测试并总结结果"
uv run ocu plan list
uv run ocu plan show <PLAN_ID>
uv run ocu plan run <PLAN_ID>
```

## 本机 OpenClaw 双向接入

OCU 已接入本地 OpenClaw `2026.7.1-2`：

- `uv run ocu openclaw status` 检查 Gateway 与插件状态；
- `uv run ocu openclaw ask "任务"` 通过现有 OpenClaw Agent 执行任务；
- OpenClaw 内新增 `ocu_plan` 工具，可创建、查看、执行和反思 OCU DAG 计划；
- OpenClaw 内新增 `ocu_knowledge`，可检索 OCU 本地知识库并返回行号引用；
- OpenClaw 继续管理渠道、模型、插件与权限；
- OCU 提供持久化 Planner、Executor、Reflection 与有限重试；
- Gateway 密钥不会复制到 OCU。

一键安装或修复：

```powershell
.\scripts\install_openclaw_integration.ps1
```

详细设计与安全边界见
[`docs/04_OPENCLAW_INTEGRATION.md`](docs/04_OPENCLAW_INTEGRATION.md)。

## 模型路由

OCU 不猜测模型是否存在，而是读取本机 Ollama 实际库存，再按能力与显存预算路由：

```powershell
uv run ocu model routes
```

当前默认分配：

- 聊天、规划、工具调用：`qwen3:8b`
- 代码：`qwen2.5-coder:7b`
- 视觉：`qwen3-vl:8b`
- 向量：`qwen3-embedding:0.6b`

## 本地知识库

```powershell
uv run ocu knowledge index
uv run ocu knowledge status
uv run ocu knowledge search "OpenClaw Ollama 配置"
```

默认知识库为 `E:\OpenClaw-Knowledge\library`。索引结果保存在
`.openclaw/knowledge.db`，不会提交到 Git。

## 本地 API

```powershell
.\scripts\start_ocu.ps1
Invoke-RestMethod http://127.0.0.1:8765/health
```

API 默认只监听 `127.0.0.1`。详细运行说明见
[`docs/05_OPERATIONS.md`](docs/05_OPERATIONS.md)。

## 安全模型

- Agent 文件工具只能访问 `OCU_WORKSPACE_ROOT`。
- `.env`、`.openclaw/`、`.git/` 和虚拟环境目录禁止读取。
- 单文件读取大小和搜索结果数量均有限制。
- Shell 工具默认关闭。
- 开启 Shell 后只允许执行配置白名单中的程序。
- 命令直接启动，不经过 Shell，不支持管道、重定向或命令拼接。
- 聊天数据库、长期记忆数据库和 `.env` 不进入 Git。

如需启用白名单命令工具：

```powershell
$env:OCU_ENABLE_SHELL_TOOL = "true"
uv run ocu chat
```

默认命令白名单：

```text
git, uv, python, pytest
```

完整配置示例见 `.env.example`。

## 测试

```powershell
uv run pytest -q
uv run ruff check src tests
```

## 路线

项目按可验证的小阶段推进：

1. Agent Runtime 与模型适配器
2. 会话、上下文摘要和长期记忆
3. 安全工作区工具
4. Reflection 与失败重新规划
5. Model Router
6. RAG 文档索引
7. MCP、插件与外部工具接入
8. API 服务和 Web UI
9. 多 Agent、Benchmark 与工作流

当前 v0.1 已完成到本地 API 与端到端运行层。Web UI、多 Agent 调度和更大规模
Benchmark 属于后续增强，不影响当前 CLI、OpenClaw 插件、Browser、ComfyUI、
MCP 接口、RAG 和本地 API 的使用。
