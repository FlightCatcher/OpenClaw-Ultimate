param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$env:UV_LINK_MODE = "copy"
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

& uv --directory $resolvedRoot lock --check
if ($LASTEXITCODE -ne 0) { throw "uv.lock is stale." }

& uv --directory $resolvedRoot run --no-sync ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }

& uv --directory $resolvedRoot run --no-sync mypy src
if ($LASTEXITCODE -ne 0) { throw "Mypy failed." }

& uv --directory $resolvedRoot run --no-sync pytest
if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }

& uv --directory $resolvedRoot build
if ($LASTEXITCODE -ne 0) { throw "Package build failed." }

& uv --directory $resolvedRoot run --no-sync python scripts\verify_databases.py .openclaw
if ($LASTEXITCODE -ne 0) { throw "Database integrity failed." }

& uv --directory $resolvedRoot run --no-sync python scripts\benchmark_vela.py
if ($LASTEXITCODE -ne 0) { throw "Foundation benchmark failed." }

$desktopRoot = Join-Path $resolvedRoot "integrations\vela-desktop"
& npm --prefix $desktopRoot test
if ($LASTEXITCODE -ne 0) { throw "VELA Desktop tests failed." }

& npm --prefix $desktopRoot audit --omit=dev
if ($LASTEXITCODE -ne 0) { throw "VELA Desktop production dependency audit failed." }

Write-Host "[OK] VELA v1.1 release checks passed."
