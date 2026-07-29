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

& uv --directory $resolvedRoot run ocu status

if ($LASTEXITCODE -ne 0) {
    throw "Unified OCU diagnostics failed."
}

& uv --directory $resolvedRoot run ocu openclaw status

if ($LASTEXITCODE -ne 0) {
    throw "OpenClaw integration verification failed."
}

& uv --directory $resolvedRoot run ocu model routes

if ($LASTEXITCODE -ne 0) {
    throw "Model route verification failed."
}

$health = Invoke-RestMethod `
    -Uri "http://127.0.0.1:$Port/health" `
    -TimeoutSec 30

if ($health.ok -ne $true) {
    throw "OCU local API is not ready."
}

Write-Host "[OK] OCU verification completed."
