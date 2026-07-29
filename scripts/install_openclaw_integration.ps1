param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command was not found: $Name"
    }
}

Assert-Command "openclaw"
Assert-Command "uv"

$resolvedProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$pluginRoot = Join-Path $resolvedProjectRoot "integrations\openclaw-plugin"
$pluginManifest = Join-Path $pluginRoot "openclaw.plugin.json"

if (-not (Test-Path -LiteralPath $pluginManifest -PathType Leaf)) {
    throw "OpenClaw plugin manifest was not found: $pluginManifest"
}

$configPathText = (& openclaw config file).Trim()

if (-not $configPathText) {
    throw "OpenClaw did not return an active config path."
}

$configPath = [Environment]::ExpandEnvironmentVariables(
    $configPathText.Replace("~", $HOME)
)
$configPath = (Resolve-Path -LiteralPath $configPath).Path
$backupRoot = Join-Path (Split-Path -Parent $configPath) "backups"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupRoot "openclaw-before-ocu-$stamp.json"
Copy-Item -LiteralPath $configPath -Destination $backupPath
Write-Host "[OK] OpenClaw config backup: $backupPath"

& openclaw plugins inspect openclaw-ultimate --json *> $null
$installed = $LASTEXITCODE -eq 0

if (-not $installed) {
    & openclaw plugins install --link $pluginRoot

    if ($LASTEXITCODE -ne 0) {
        throw "Could not link the OpenClaw Ultimate plugin."
    }
}

& openclaw config set `
    "plugins.entries.openclaw-ultimate.config.projectRoot" `
    $resolvedProjectRoot

if ($LASTEXITCODE -ne 0) {
    throw "Could not configure the OpenClaw Ultimate project root."
}

$tools = (& openclaw config get tools | ConvertFrom-Json)
$alsoAllow = @($tools.alsoAllow)

foreach ($toolName in @("ocu_plan", "ocu_knowledge", "browser")) {
    if ($alsoAllow -notcontains $toolName) {
        $alsoAllow += $toolName
    }
}

$alsoAllowJson = ConvertTo-Json -InputObject @($alsoAllow) -Compress
& openclaw config set tools.alsoAllow $alsoAllowJson --strict-json

if ($LASTEXITCODE -ne 0) {
    throw "Could not allow the OCU and Browser tools."
}

& openclaw config validate

if ($LASTEXITCODE -ne 0) {
    throw "OpenClaw config validation failed."
}

& openclaw plugins inspect openclaw-ultimate --runtime --json *> $null

if ($LASTEXITCODE -ne 0) {
    throw "OpenClaw could not load the OpenClaw Ultimate plugin."
}

if (-not $SkipRestart) {
    & openclaw gateway restart --safe

    if ($LASTEXITCODE -ne 0) {
        throw "OpenClaw Gateway safe restart failed."
    }

    $ready = $false

    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $status = Invoke-RestMethod `
                -Uri "http://127.0.0.1:18789/readyz" `
                -TimeoutSec 3

            if ($status.ready -eq $true) {
                $ready = $true
                break
            }
        }
        catch {
            # Gateway is briefly unavailable while restarting.
        }

        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        throw "OpenClaw Gateway did not become ready within 60 seconds."
    }
}

& uv --directory $resolvedProjectRoot run ocu openclaw status

if ($LASTEXITCODE -ne 0) {
    throw "OCU could not connect back to OpenClaw."
}

Write-Host "[OK] Bidirectional OCU <-> OpenClaw integration is ready."
