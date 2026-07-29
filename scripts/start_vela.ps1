param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "start_ocu.ps1") `
    -ProjectRoot $ProjectRoot `
    -Port $Port

if ($LASTEXITCODE -ne 0) {
    throw "VELA service could not be started."
}

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port/"
}

Write-Host "[OK] VELA Command Deck: http://127.0.0.1:$Port/"
