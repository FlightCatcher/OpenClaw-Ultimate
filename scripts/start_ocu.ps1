param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$executable = Join-Path $resolvedRoot ".venv\Scripts\ocu.exe"
$stateRoot = Join-Path $resolvedRoot ".openclaw"
$logRoot = Join-Path $stateRoot "logs"
$pidPath = Join-Path $stateRoot "ocu-api.pid"

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "OCU environment is missing. Run .\bootstrap.ps1 first."
}

$existing = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($existing) {
    try {
        $health = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$Port/health" `
            -TimeoutSec 5

        if ($health.ok -eq $true) {
            $owner = (
                Get-NetTCPConnection `
                    -LocalPort $Port `
                    -State Listen `
                    -ErrorAction Stop |
                Select-Object -First 1
            ).OwningProcess
            New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
            Set-Content `
                -LiteralPath $pidPath `
                -Value $owner `
                -NoNewline
            Write-Host "[OK] OCU API is already ready on port $Port."
            exit 0
        }
    }
    catch {
        # The listener exists but is not the OCU API.
    }

    throw "Port $Port is already used by another process."
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$stdoutPath = Join-Path $logRoot "api.stdout.log"
$stderrPath = Join-Path $logRoot "api.stderr.log"
$process = Start-Process `
    -FilePath $executable `
    -ArgumentList @(
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "$Port"
    ) `
    -WorkingDirectory $resolvedRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$Port/health" `
            -TimeoutSec 5

        if ($health.ok -eq $true) {
            $owner = (
                Get-NetTCPConnection `
                    -LocalPort $Port `
                    -State Listen `
                    -ErrorAction Stop |
                Select-Object -First 1
            ).OwningProcess
            Set-Content `
                -LiteralPath $pidPath `
                -Value $owner `
                -NoNewline
            Write-Host "[OK] OCU API ready: http://127.0.0.1:$Port"
            Write-Host "[OK] PID: $owner"
            exit 0
        }
    }
    catch {
        # Startup is still in progress.
    }

    Start-Sleep -Seconds 1
}

$listener = Get-NetTCPConnection `
    -LocalPort $Port `
    -State Listen `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($listener) {
    Stop-Process `
        -Id $listener.OwningProcess `
        -Force `
        -ErrorAction SilentlyContinue
}

throw "OCU API did not become ready within 30 seconds."
