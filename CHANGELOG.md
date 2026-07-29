# Changelog

## 1.0.2 - 2026-07-29

- Limited GitHub Release uploads to the VELA wheel and source archive.

## 1.0.1 - 2026-07-29

- Fixed the governed shell runner's Windows creation flag lookup so Linux type
  checking and release CI remain portable.

## 1.0.0 - 2026-07-29

- Rebranded the local agent as VELA while preserving OCU compatibility.
- Added the local Command Deck UI and expanded v1 API.
- Added persisted confirmations, audit events, database migrations and plan controls.
- Added governed memory metadata, expiration and archival.
- Added PDF, DOCX, HTML, CSV, JSON and source-code knowledge extraction.
- Enabled and verified the bundled read-only `vela-local` MCP server.
- Added Windows desktop installation, backup, integrity and release tooling.
- Added Windows/Linux CI and tagged release packaging.

## 0.1.0 - 2026-07-29

### Added

- Async Agent Runtime with bounded tool loops.
- Persistent sessions, rolling summaries and semantic memory.
- Structured Planner, DAG Executor, Reflection, bounded retry and plan revisions.
- Bidirectional OpenClaw plugin and CLI integration.
- Deterministic OpenClaw Browser reads.
- Shared OpenClaw ComfyUI workflow integration with real image generation.
- Hardware-aware Ollama model inventory and task routing.
- Allowlisted MCP stdio client.
- Incremental local knowledge indexing, hybrid retrieval and line citations.
- Loopback-only local JSON API and unified diagnostics.
- Repeatable bootstrap, OpenClaw integration, start, stop and verification scripts.

### Security

- OpenClaw Gateway credentials remain owned by OpenClaw.
- Workspace file tools enforce root boundaries.
- Shell remains disabled by default and uses a command allowlist when enabled.
- MCP servers are opt-in and loaded only from a local command allowlist.
- ComfyUI generation uses one preconfigured workflow rather than arbitrary workflow paths.
- The local API rejects non-loopback binding unless explicitly enabled.
