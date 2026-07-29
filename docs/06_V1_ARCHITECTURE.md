# VELA v1.0 Architecture

VELA 是 OpenClaw-Ultimate 的产品化名称。v1.0 保持以下兼容边界：

- 仓库路径和 GitHub 仓库名保持不变。
- Python 包继续使用 `openclaw_ultimate`。
- `ocu` CLI 继续可用，并新增等价的 `vela` CLI。
- OpenClaw 插件 ID 保持 `openclaw-ultimate`。
- `ocu_plan` 和 `ocu_knowledge` 工具名保持不变。
- 原有 sessions、memory、plans 和 knowledge SQLite 数据库原地迁移。

## Runtime

核心路径：

```text
Request
→ Agent Runtime
→ Planner
→ Task DAG
→ Executor
→ Model / Tool
→ Verification
→ Reflection
→ Retry or Candidate Revision
→ Persistent Result
```

## Control plane

`.openclaw/governance.db` 保存：

- `schema_migrations`
- `audit_events`
- `confirmations`
- `plan_controls`

任务控制使用协作式中断：Executor 在步骤边界读取 `pause` 或 `cancel` 请求。正在运行的
模型/工具调用不会被强制杀死，避免留下损坏的外部状态。

## UI

Command Deck 由 Python 本地 API 直接提供静态资源，不使用云端 CDN、外部字体或遥测。
所有请求都指向 `127.0.0.1`。
