# OpenClaw Ultimate

本地优先、模块化、可扩展的 AI Agent 平台。

OpenClaw Ultimate 当前可以连接 Ollama，通过异步 Agent Runtime
完成多轮对话、工具调用、持久化会话、滚动摘要和跨会话语义记忆。

## 当前能力

- OpenAI-Compatible 聊天与 Embedding 适配器
- Ollama 本地模型接入
- 多步骤 Agent 与同步/异步工具调用
- SQLite 持久化会话
- Token 预算与滚动会话摘要
- 基于向量检索的长期记忆
- 受工作区边界保护的文件列表、读取和文本搜索
- 默认关闭的白名单命令执行
- 环境、模型和工作区健康检查

## 快速开始

```powershell
.\bootstrap.ps1
uv run ocu doctor
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
4. Planner 与任务执行状态
5. RAG 文档索引
6. MCP 与外部工具接入
7. API 服务和 Web UI
8. 多 Agent、反思与工作流
