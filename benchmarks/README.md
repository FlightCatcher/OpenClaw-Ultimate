# VELA Benchmarks

VELA v1.0 ships with a deterministic local foundation benchmark. It measures
plan persistence and rule-based verification without network access or model
downloads.

Run it from the repository root:

```powershell
uv run python scripts/benchmark_vela.py
```

The command prints JSON so results can be archived or compared between
releases. Model quality is intentionally excluded because it depends on the
locally selected Ollama model and hardware.
