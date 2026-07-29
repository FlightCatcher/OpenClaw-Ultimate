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

VELA 复用 OpenClaw 原生 Dashboard，保留其图标、布局、会话管理、认证和插件机制。
`scripts/apply_vela_openclaw_ui.ps1` 只添加可重复应用的品牌层，不改写 OpenClaw
内部协议或前端程序包。OpenClaw 更新覆盖本地静态文件后，重新运行集成安装脚本即可。

原先由 Python API 提供的 Command Deck 保留为兼容界面，但不再是默认入口。默认
桌面入口打开 `127.0.0.1:18789` 的已认证 Dashboard；兼容 API 继续只监听
`127.0.0.1:8765`。
