
$ErrorActionPreference = "Stop"
$env:UV_LINK_MODE = "copy"
uv python pin 3.12
uv sync --dev --locked --link-mode copy
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
uv run ocu doctor
