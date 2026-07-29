# Contributing to VELA

1. Use Python 3.12 and the locked `uv` environment.
2. Keep changes focused and preserve OCU compatibility unless a migration is documented.
3. Do not commit `.env`, `.openclaw`, model files, credentials or generated outputs.
4. Add tests for every behavior change.
5. Run `.\scripts\release_check.ps1` before opening a pull request.

Commit messages use conventional prefixes such as `feat:`, `fix:`, `docs:`, `test:` and
`chore:`.
