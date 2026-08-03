# Changelog

## VELA Desktop 4.16.0 — reliable image completion - 2026-08-03

- Restored rendering for historical ComfyUI records persisted as relative `view?...` URLs when the underlying output still exists.
- Added deterministic desktop media URL tests for ComfyUI, local files and absolute web data.
- Kept local file media behind the authenticated, workspace-restricted desktop endpoint.
- Automatically routes explicit natural-language image requests to the local ComfyUI pipeline without requiring the Image button first.
- Persists direct image prompts together with their generated media so image conversations survive a desktop restart.
- Correctly ends the working state when OpenClaw returns histories in newest-first or oldest-first order.
- Prevents duplicate OCU API processes by probing the loopback port before running deep health checks or starting a server.
- Preserved the VELA 1.8 liquid-glass desktop experience while hardening image history.

## VELA 1.6.0 — liquid glass UI and image model studio - 2026-08-03

- Rebuilt the desktop layout around a stable grid so the workflow deck, chat stream, composer and workspace panel no longer cover each other.
- Added neutral black, graphite and ivory liquid-glass surfaces with animated ambient light, spring entrances, message transitions, panel expansion and hover feedback.
- Added compact subject presets for anime characters, reference-locked characters, realistic portraits, landscapes and product photography.
- Added image engine choices for Anime/Animagine XL, Fast SDXL, FLUX.2 reference and realistic Juggernaut XL routing.
- Added a realistic image route that selects the photography checkpoint when the user chooses the realistic engine.
- Bumped renderer cache keys and desktop package version to 4.12.0 so the installed desktop app cannot silently reuse the previous UI.

## VELA 1.5 UI refinement - 2026-08-03

- Reworked the desktop shell into a monochrome black, white and graphite glass system.
- Removed visible blue accents, animated scan effects and colorful status indicators.
- Replaced workspace glyphs with larger, restrained line icons and improved hit areas.
- Simplified the command deck, composer, image studio, status cards and session list.
- Preserved light and dark modes while keeping both themes within the same neutral visual language.

## VELA 1.5.0 - 2026-08-03

- Added a live local health badge for the OpenClaw Gateway, ComfyUI, Ollama and OCU services.
- Added memory-pressure and model-library resource diagnostics without loading any model.
- Added a real image-generation cancellation path that interrupts the active ComfyUI job, including 4K upscaling.
- Exposed image job phase and cancellation state through the local diagnostics and image-status APIs.
- Added an explicit VELA 1.5 release marker to the desktop title bar and bootstrap metadata.
- Rebuilt and deployed the portable desktop executable to the local OpenClaw app directory.

## 1.1.1 - 2026-07-30

- Refined VELA Desktop with a restrained black, white and graphite visual system.
- Replaced the previous colorful mark with a minimal monochrome VELA icon across the title bar, welcome screen, messages and desktop shortcut.
- Added spring-like entrance, message, control, dialog and toast animations with reduced-motion support.
- Fixed stale icon caching and restored the welcome screen scroll position when starting a new conversation.
- Rebuilt and installed VELA Desktop 4.1.1 after validating a real DeepSeek conversation.

## 1.1.0 - 2026-07-29

- Shipped VELA Desktop as a standalone Windows application instead of a browser launcher.
- Added a black, graphite and electric-blue interface with a new original VELA icon.
- Preserved existing OpenClaw sessions, Gateway authentication, tools, attachments and ComfyUI.
- Verified a real DeepSeek conversation through the packaged desktop executable.
- Added reproducible desktop source, build, install and launch automation.
- Retired the old OpenClaw executable and browser shortcuts after successful validation.

## 1.0.4 - 2026-07-29

- Reused the original OpenClaw Dashboard as VELA's primary local interface.
- Preserved the original OpenClaw icon, layout, sessions and runtime internals.
- Added an idempotent VELA branding layer with automatic local UI backups.
- Kept DeepSeek API as the primary chat model and Ollama as the local fallback.
- Updated the desktop launcher to open the authenticated OpenClaw Dashboard.

## 1.0.3 - 2026-07-29

- Fixed Windows-relative MCP configuration resolution that could make local chat return HTTP 500.
- Reused API stores and the chat agent to avoid repeated SQLite initialization and UI lock waits.
- Added an original AI-generated VELA avatar and a black, graphite and electric-blue local UI.
- Improved chat progress, local-only status, structured errors and one-click retry.

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
