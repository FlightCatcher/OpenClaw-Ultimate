# VELA Security Model

## Trust boundaries

VELA 把模型输出、网页、文档、MCP 结果和工具输出视为不可信数据。它们不能覆盖系统
策略，也不能自行获得新的权限。

## Workspace

- 路径必须解析在 `workspace_root` 内。
- `.git`、`.openclaw`、虚拟环境和环境变量文件默认不可读。
- 文本读取有文件大小和结果数量限制。

## Commands

- 使用 `subprocess` 参数数组并保持 `shell=False`。
- 只有配置白名单中的可执行程序可运行。
- Ruff、Mypy、Pytest 和只读 Git 命令可直接执行。
- Git 写入、任意 Python 和其他可变更命令需要一次性确认。
- 批准和具体命令指纹绑定，使用后立即失效。

## Confirmations

确认状态为：

```text
pending → approved → consumed
        ↘ rejected
```

一次批准不会授权未来操作。

## Local API

- 默认只监听 `127.0.0.1`。
- 非回环监听必须显式启用。
- 请求体有大小限制。
- API 不记录请求正文、密钥或模型上下文。

## MCP

- 服务命令来自本地 JSON 白名单。
- `{project_root}` 只由 VELA 配置展开。
- 模型只能选择服务公开的工具，不能改变服务启动命令。
- 每次 stdio 调用具有超时和独立生命周期。
