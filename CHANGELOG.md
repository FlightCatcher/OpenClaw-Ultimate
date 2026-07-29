# Changelog

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
