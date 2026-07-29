param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$pidPath = Join-Path $resolvedRoot ".openclaw\ocu-api.pid"

if (-not (Test-Path -LiteralPath $pidPath -PathType Leaf)) {
    Write-Host "[OK] No VELA API PID file exists."
    exit 0
}

$rawPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
$processId = 0

if (-not [int]::TryParse($rawPid, [ref]$processId)) {
    throw "VELA API PID file is invalid: $pidPath"
}

$processInfo = Get-CimInstance `
    Win32_Process `
    -Filter "ProcessId = $processId" `
    -ErrorAction SilentlyContinue

if ($processInfo) {
    $commandLine = [string]$processInfo.CommandLine

    if (
        $commandLine -notmatch "(ocu|vela)(\.exe)?[\""]?\s+serve" -or
        $commandLine -notmatch [regex]::Escape($resolvedRoot)
    ) {
        throw "PID $processId does not belong to this VELA API."
    }

    Stop-Process -Id $processId
    Write-Host "[OK] VELA API stopped (PID $processId)."
}
else {
    Write-Host "[OK] VELA API process is already stopped."
}

Remove-Item -LiteralPath $pidPath -Force
