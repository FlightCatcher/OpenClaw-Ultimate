
$ErrorActionPreference = "Stop"
uv run ruff check .
uv run pytest
Write-Host "All checks passed." -ForegroundColor Green
