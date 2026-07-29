# OCU 本机运行与维护

## 当前部署

- 项目：`E:\Projects\OpenClaw-Ultimate`
- OpenClaw Gateway：`127.0.0.1:18789`
- VELA Dashboard（原生 OpenClaw UI）：`127.0.0.1:18789`
- 兼容 API：`127.0.0.1:8765`
- Ollama：`127.0.0.1:11434`
- ComfyUI：`127.0.0.1:8188`
- 知识库：`E:\OpenClaw-Knowledge\library`
- 模型库：`E:\AI-Models`

所有服务默认只监听本机。OCU 不复制 OpenClaw Gateway 密钥。

## 首次初始化

```powershell
cd E:\Projects\OpenClaw-Ultimate
.\bootstrap.ps1
.\scripts\install_openclaw_integration.ps1
.\scripts\install_vela.ps1
uv run ocu knowledge index
.\scripts\verify_ocu.ps1 -Full
```

## 日常启动

双击桌面的 **VELA AI**，或执行：

```powershell
.\scripts\start_vela.ps1
uv run ocu status
```

启动器会复用 OpenClaw Dashboard 和原图标，并以当前 Gateway token 打开页面。
聊天主模型来自 OpenClaw 配置，当前为 `deepseek/deepseek-v4-flash`；Ollama
`qwen3:8b` 仅作为本地回退。

如需调试兼容 API，再单独运行：

```powershell
.\scripts\start_ocu.ps1
```

## 日常停止

```powershell
.\scripts\stop_ocu.ps1
```

停止脚本只会终止 PID 文件记录且命令行属于当前项目的 OCU 进程。

## 常用命令

```powershell
uv run ocu chat "检查当前项目状态"
uv run ocu openclaw status
uv run ocu model routes
uv run ocu knowledge status
uv run ocu knowledge search "OpenClaw Ollama 配置"
uv run ocu plan list
```

## 兼容 API

健康检查：

```text
GET http://127.0.0.1:8765/health
```

知识库检索：

```text
POST http://127.0.0.1:8765/v1/knowledge/search
{"query":"OpenClaw Ollama 配置","limit":5}
```

聊天：

```text
POST http://127.0.0.1:8765/v1/chat
{"message":"只回复 OCU_API_OK"}
```

计划：

```text
POST /v1/plans
GET  /v1/plans/<PLAN_ID>
POST /v1/plans/<PLAN_ID>/run
POST /v1/plans/<PLAN_ID>/reflect
```

## 知识库策略

默认仅索引 1 MB 以下的 Markdown、文本和 RST 文件。这样会覆盖当前聚焦文档与
Ollama 文档，并跳过几十 MB 的仓库合并镜像。索引是增量的，文件未变化时不会重新
计算向量。

如需扩大单文件上限，在 `.env` 调整：

```text
OCU_KNOWLEDGE_MAX_FILE_BYTES=5000000
```

然后重新运行：

```powershell
uv run ocu knowledge index
```

## 故障排查

```powershell
uv run ocu status
uv run ocu openclaw status
Get-Content .openclaw\logs\api.stderr.log
.\scripts\verify_ocu.ps1
```

完整回归：

```powershell
.\scripts\verify_ocu.ps1 -Full
```
