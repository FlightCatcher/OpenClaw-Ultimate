# VELA Data, Migration and Recovery

## Local databases

```text
.openclaw/sessions.db
.openclaw/memory.db
.openclaw/plans.db
.openclaw/knowledge.db
.openclaw/governance.db
```

所有数据库启用 WAL 和事务。v1.0 启动时以幂等方式创建缺失表和字段，不覆盖已有数据。

## Memory migration

旧记忆记录自动获得安全默认值：

- `memory_type=fact`
- `importance=0.5`
- `sensitivity=normal`
- `archived=false`

## Backup

```powershell
.\scripts\backup_vela.ps1
```

默认输出到 `E:\AI-Backups\VELA`。备份文件不上传 GitHub。

脚本使用 SQLite 在线备份 API 创建一致快照，因此 VELA 运行时也可以安全备份。
日志、PID、WAL/SHM 临时文件和类型检查缓存不会进入归档。每个归档都包含
`manifest.json`，并在创建前对快照执行完整性检查。

## Integrity

```powershell
uv run python scripts\verify_databases.py .openclaw
```

脚本对每个 SQLite 数据库运行 `PRAGMA integrity_check`，并输出表数量和文件大小。
