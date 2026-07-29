param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    throw "OpenClaw was not found."
}

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
& (Join-Path $PSScriptRoot "apply_vela_openclaw_ui.ps1")

if ($LASTEXITCODE -ne 0) {
    throw "The VELA brand layer could not be applied."
}

& openclaw plugins inspect openclaw-ultimate --runtime --json *> $null

if ($LASTEXITCODE -ne 0) {
    & (Join-Path $PSScriptRoot "install_openclaw_integration.ps1") `
        -ProjectRoot $resolvedRoot
}
else {
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:18789/readyz" -TimeoutSec 3
    }
    catch {
        $ready = $null
    }

    if ($null -eq $ready -or $ready.ready -ne $true) {
        & openclaw gateway restart --safe

        if ($LASTEXITCODE -ne 0) {
            throw "The VELA/OpenClaw gateway could not be started."
        }
    }
}

if ($NoBrowser) {
    & openclaw dashboard --no-open
}
else {
    & openclaw dashboard --yes
}

if ($LASTEXITCODE -ne 0) {
    throw "The VELA Dashboard could not be opened."
}

Write-Host "[OK] VELA is using the original OpenClaw Dashboard and icon."
