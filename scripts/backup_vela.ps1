param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$BackupRoot = "E:\AI-Backups\VELA",
    [switch]$IncludeOpenClawConfig
)

$ErrorActionPreference = "Stop"
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$arguments = @(
    "--directory",
    $resolvedRoot,
    "run",
    "python",
    "scripts\backup_vela.py",
    "--project-root",
    $resolvedRoot,
    "--backup-root",
    $BackupRoot
)

if ($IncludeOpenClawConfig) {
    $arguments += "--include-openclaw-config"
}

& uv @arguments
if ($LASTEXITCODE -ne 0) {
    throw "VELA backup failed."
}
