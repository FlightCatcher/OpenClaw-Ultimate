param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    throw "OpenClaw was not found."
}

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$executable = Join-Path $env:USERPROFILE ".openclaw\apps\openclaw-desktop\dist\VELA-Desktop.exe"

& openclaw plugins inspect openclaw-ultimate --runtime --json *> $null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $PSScriptRoot "install_openclaw_integration.ps1") `
        -ProjectRoot $resolvedRoot
}

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    & (Join-Path $PSScriptRoot "install_vela.ps1") -ProjectRoot $resolvedRoot
}

Start-Process -FilePath $executable -WorkingDirectory (Split-Path -Parent $executable)
Write-Host "[OK] Native VELA desktop started."
