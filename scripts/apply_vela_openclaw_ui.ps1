param(
    [string]$OpenClawModuleRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $OpenClawModuleRoot) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found; the OpenClaw installation directory cannot be discovered."
    }

    $npmRoot = (& npm root -g).Trim()
    $OpenClawModuleRoot = Join-Path $npmRoot "openclaw"
}

$moduleRoot = (Resolve-Path -LiteralPath $OpenClawModuleRoot).Path
$controlUiRoot = Join-Path $moduleRoot "dist\control-ui"
$indexPath = Join-Path $controlUiRoot "index.html"
$manifestPath = Join-Path $controlUiRoot "manifest.webmanifest"
$sourceBranding = Join-Path (Split-Path -Parent $PSScriptRoot) `
    "integrations\openclaw-ui\vela-branding.js"
$targetBranding = Join-Path $controlUiRoot "vela-branding.js"
$marker = "data-vela-openclaw-branding"

foreach ($requiredPath in @($indexPath, $manifestPath, $sourceBranding)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required UI file was not found: $requiredPath"
    }
}

$index = Get-Content -LiteralPath $indexPath -Raw
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

if ($index -notmatch $marker) {
    $backupRoot = Join-Path $HOME ".openclaw\backups"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $backupRoot "control-ui-before-vela-$stamp"
    New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
    Copy-Item -LiteralPath $indexPath -Destination (Join-Path $backupPath "index.html")
    Copy-Item -LiteralPath $manifestPath -Destination (
        Join-Path $backupPath "manifest.webmanifest"
    )
    Write-Host "[OK] Original OpenClaw UI metadata backed up: $backupPath"

    $index = $index.Replace(
        "<title>OpenClaw Control</title>",
        "<title>VELA · Local Agent</title>"
    )
    $brandingTag = (
        '    <script src="./vela-branding.js" ' +
        'data-vela-openclaw-branding></script>' +
        [Environment]::NewLine
    )
    $moduleTag = '    <script type="module" crossorigin '

    if (-not $index.Contains($moduleTag)) {
        throw "The OpenClaw UI entry module marker was not found."
    }

    $index = $index.Replace($moduleTag, $brandingTag + $moduleTag)
    Set-Content -LiteralPath $indexPath -Value $index -Encoding utf8
}

Copy-Item -LiteralPath $sourceBranding -Destination $targetBranding -Force

$manifest.name = "VELA Control"
$manifest.short_name = "VELA"
$manifest.description = "VELA local AI agent powered by OpenClaw"
$manifest | ConvertTo-Json -Depth 10 | Set-Content `
    -LiteralPath $manifestPath `
    -Encoding utf8

Write-Host "[OK] OpenClaw Dashboard is branded as VELA."
Write-Host "[OK] Original OpenClaw icons and internal runtime remain unchanged."
