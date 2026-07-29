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

VELA Desktop 是独立打包的 Windows Electron 应用。它保留 OpenClaw Gateway 协议、
认证、会话和工具兼容性，但拥有独立的 VELA 图标、黑灰蓝视觉系统和窗口生命周期。
桌面端只在回环地址 `127.0.0.1:18790` 提供渲染资源，再连接
`127.0.0.1:18789` 的 OpenClaw Gateway，因此不会打开或依赖浏览器窗口。

桌面端源码位于 `integrations/vela-desktop`，安装脚本会构建
`VELA-Desktop.exe` 并创建桌面快捷方式。OpenClaw Dashboard 与 Python Command Deck
保留为兼容和诊断界面，但不再是默认入口；兼容 API 继续只监听 `127.0.0.1:8765`。
