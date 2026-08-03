# VELA

> **Verified Executive Local Agent · 维澜**
>
> Think locally. Act deliberately.

VELA 是一个本地优先、可验证、可扩展的 AI Agent 操作系统。它通过兼容层增强
OpenClaw，并将 Ollama、任务规划、DAG 执行、长期记忆、RAG、工具、ComfyUI、
MCP、安全确认和审计记录组合为一个真正可执行的本地工作伙伴。

本仓库原名 **OpenClaw-Ultimate（OCU）**。`ocu` 命令、Python 包名、OpenClaw
插件 ID 和已有 SQLite 数据库继续兼容；v1.0 的产品名称和 UI 为 **VELA**。

命名角色与严格参考生图采用可审计的
[VELA 角色还原流程](docs/IMAGE_IDENTITY_PIPELINE.md)：先研究和校验参考图，
再按题材路由模型，顺序生成并通过本地 90 分身份门槛后才向 UI 发布。

## v1.0 能做什么

- 将自然语言目标转换为结构化 DAG，并按依赖执行。
- 通过 Planner、Executor、Reflection、有限重试和 Replanning 处理复杂任务。
- 双向连接本机 OpenClaw，提供 `ocu_plan` 和 `ocu_knowledge` 工具。
- 根据聊天、代码、规划、视觉、工具调用和向量任务路由本地 Ollama 模型。
- 在本地长期记忆中管理类型、重要度、敏感度、有效期和归档状态。
- 索引 Markdown、文本、代码、JSON、CSV、HTML、DOCX 和 PDF，并返回行号引用。
- 使用 OpenClaw Browser 读取公开网页，使用 ComfyUI 生成图片。
- 通过白名单 stdio MCP 调用工具；内置 `vela-local` MCP 服务用于真实链路验收。
- 对写入、删除和高风险命令执行一次性人工确认，并留下 SQLite 审计记录。
- 通过独立的 VELA Windows 桌面端管理对话、附件、生图和本地连接状态。
- 备份本地状态、检查数据库完整性，并通过 Windows/Linux CI 自动回归。

## 系统结构

```text
User
  │
  ├── VELA Desktop（原生 Windows 应用）
  ├── CLI
  └── Compatibility API
        │
        ▼
Agent Runtime
  ├── Planner → DAG → Executor
  ├── Reflection → Retry → Replanning
  ├── Memory → RAG
  ├── Model Router → Ollama
  ├── Tool Registry → Browser / ComfyUI / MCP / Workspace
  └── Governance → Confirmation / Audit / Task Control
```

## 针对当前电脑优化

默认配置针对以下机器校准：

- Windows 11
- AMD Ryzen 5 3600
- NVIDIA RTX 3060 Ti 8GB
- 16GB RAM
- 模型库存：`E:\AI-Models`

VELA 默认只让一个 4B–8B 模型常驻显存，驻留预算为 6.5 GiB，不会同时加载多个
大型模型。

## 启动本地 UI

首次安装：

```powershell
.\bootstrap.ps1
.\scripts\install_openclaw_integration.ps1
.\scripts\install_vela.ps1
```

之后双击桌面的 **VELA**，或运行：

```powershell
.\scripts\start_vela.ps1
```

桌面快捷方式会打开独立的 Windows 应用，不会打开浏览器。VELA Desktop 通过本机
OpenClaw Gateway 保留既有会话、工具、附件、生图能力和认证：

```text
VELA Desktop → 127.0.0.1:18790 → OpenClaw Gateway 127.0.0.1:18789
```

聊天继续使用当前 OpenClaw 配置中的 DeepSeek API 主模型；本地 Ollama 模型只作为
故障回退。浏览器 Dashboard 和独立的 `8765` API/UI 仅保留用于兼容和调试，不再是
默认用户界面。

需要前台运行兼容 API 时：

```powershell
uv run vela ui
```

## 常用命令

```powershell
uv run vela status
uv run vela chat
uv run vela plan create "分析项目并给出下一步"
uv run vela plan list
uv run vela knowledge index
uv run vela knowledge search "OpenClaw Ollama 配置"
uv run vela memory list
uv run vela openclaw status
```

旧命令仍然有效：

```powershell
uv run ocu status
```

## 兼容 API

主要端点：

- `GET /`：旧版兼容页面（非默认 UI）
- `GET /health`：统一健康状态
- `GET /v1/meta`：品牌与版本
- `POST /v1/chat`：本地对话
- `GET|POST /v1/plans`：任务计划
- `POST /v1/plans/<id>/run|pause|resume|cancel|reflect`
- `GET|POST /v1/knowledge/status|search|index`
- `GET|POST|DELETE /v1/memories`
- `GET /v1/confirmations`
- `POST /v1/confirmations/<id>/approve|reject`
- `GET /v1/audit`
- `GET /v1/mcp/status`
- `POST /v1/mcp/test`

默认拒绝非回环地址绑定。除非明确修改配置，否则不会暴露到局域网或互联网。

## 安全原则

- 文件访问限制在配置的工作区内。
- `.git`、`.venv`、`.openclaw`、`.env` 和密钥文件受保护。
- Shell 不经过命令解释器，只能运行本地白名单命令。
- 只读命令直接执行；写入和高风险命令必须获得一次性批准。
- MCP 服务及启动命令来自本地白名单，不接受模型提供的进程命令。
- 高风险操作、确认结果和 API 操作写入本地审计数据库。
- 自动重试有严格上限，权限错误和重复错误不会无限重试。

详见 [安全模型](docs/07_SECURITY.md)。

## 验证与发布

```powershell
.\scripts\verify_ocu.ps1 -Full
.\scripts\release_check.ps1
```

发布检查包括：

- Ruff
- Mypy
- Pytest
- 锁文件一致性
- Python wheel/sdist 构建
- SQLite 完整性检查
- OpenClaw、Ollama、ComfyUI、MCP 和知识库实时诊断

## 数据与备份

运行状态位于 `.openclaw`，该目录不会提交到 Git。创建本地备份：

```powershell
.\scripts\backup_vela.ps1
```

默认备份到 `E:\AI-Backups\VELA`。只有显式添加
`-IncludeOpenClawConfig` 时才会包含可能带凭据的 OpenClaw 配置。

## 开发

```powershell
uv sync --dev --locked
uv run ruff check .
uv run mypy src
uv run pytest
uv build
```

Python 固定为 3.12。依赖由 `uv.lock` 锁定。

## 文档

- [系统哲学](docs/00_SYSTEM_PHILOSOPHY.md)
- [总体架构](docs/01_ARCHITECTURE.md)
- [Agent Loop](docs/02_AGENT_LOOP.md)
- [硬件配置](docs/03_HARDWARE_PROFILE.md)
- [OpenClaw 集成](docs/04_OPENCLAW_INTEGRATION.md)
- [运行维护](docs/05_OPERATIONS.md)
- [v1.0 架构与兼容策略](docs/06_V1_ARCHITECTURE.md)
- [安全模型](docs/07_SECURITY.md)
- [数据迁移与恢复](docs/08_DATA_AND_RECOVERY.md)

## License

MIT
