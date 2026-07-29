# 架构

```text
User
  ↓
CLI
  ├─ Session Store (SQLite)
  ├─ Planner Store (SQLite)
  ├─ Rolling Summary
  └─ Semantic Memory (Embedding + SQLite)
  ↓
Context Window Builder
  ↓
Agent Runtime
  ├─ Planner (Task Graph / DAG)
  ├─ Executor (step state / result persistence)
  ├─ OpenAI-Compatible Model
  └─ Tool Registry
       ├─ Workspace read/search tools
       ├─ Optional allowlisted command runner
       └─ Long-term memory tool
  ↓
Ollama
```

## 模块边界

- `core/`：消息、工具注册和 Agent Runtime。
- `models/`：聊天与 Embedding 模型适配器。
- `sessions/`：会话、消息和滚动摘要持久化。
- `memory/`：摘要、长期记忆和语义检索。
- `tools/`：工作区访问策略与受限命令执行。
- `planner/`：结构化计划、DAG 校验、计划执行和状态持久化。
- `context.py`：Token 估算和上下文窗口选择。
- `app.py`：默认 Agent 及内置工具装配。
- `cli.py`：聊天、会话和记忆命令。

## 设计约束

- 本地数据默认不离开本机。
- 模型适配器不依赖具体供应商 SDK。
- Runtime 不直接了解 CLI、SQLite 或 Ollama。
- 工具通过明确的 JSON Schema 暴露给模型。
- 文件和命令工具必须经过工作区策略。
- 危险能力默认关闭，并由配置显式启用。
