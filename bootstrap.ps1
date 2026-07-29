
$ErrorActionPreference = "Stop"
uv python pin 3.12
if (Test-Path ".venv") { Remove-Item -Recurse -Force ".venv" }
uv sync --dev
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
uv run ocu doctor
