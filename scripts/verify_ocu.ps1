param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$Port = 8765,
    [switch]$Full
)

$ErrorActionPreference = "Stop"
$env:UV_LINK_MODE = "copy"

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

& uv --directory $resolvedRoot run ruff check .

if ($LASTEXITCODE -ne 0) {
    throw "Ruff checks failed."
}

& uv --directory $resolvedRoot run mypy src

if ($LASTEXITCODE -ne 0) {
    throw "Mypy checks failed."
}

if ($Full) {
    & uv --directory $resolvedRoot run pytest

    if ($LASTEXITCODE -ne 0) {
        throw "Pytest failed."
    }
}

& uv --directory $resolvedRoot run vela status

if ($LASTEXITCODE -ne 0) {
    throw "Unified VELA diagnostics failed."
}

& uv --directory $resolvedRoot run vela openclaw status

if ($LASTEXITCODE -ne 0) {
    throw "OpenClaw integration verification failed."
}

& uv --directory $resolvedRoot run vela model routes

if ($LASTEXITCODE -ne 0) {
    throw "Model route verification failed."
}

$health = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/health" `
    -TimeoutSec 30

if ($health.ok -ne $true) {
    throw "VELA local API is not ready."
}

$meta = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/v1/meta" `
    -TimeoutSec 30

if ($meta.data.version -ne "1.0.2" -or $meta.data.name -ne "VELA") {
    throw "VELA UI/API metadata is not v1.0.2."
}

$mcp = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/v1/mcp/status" `
    -TimeoutSec 30

if ($mcp.data.enabled -ne $true) {
    throw "VELA MCP integration is not enabled."
}

& uv --directory $resolvedRoot run python scripts\verify_databases.py .openclaw
if ($LASTEXITCODE -ne 0) {
    throw "VELA database integrity verification failed."
}

Write-Host "[OK] VELA verification completed."
