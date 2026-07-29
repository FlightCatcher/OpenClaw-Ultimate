# OpenClaw Integration

## Outcome

OpenClaw Ultimate (OCU) is connected to the existing local OpenClaw
installation in both directions:

```text
OCU
  └─ OpenClawCliClient
       └─ official `openclaw agent --json`
            └─ local OpenClaw Gateway
                 └─ existing agents, models, plugins and permissions

OpenClaw Agent
  ├─ `ocu_plan` plugin tool
  └─ `ocu_knowledge` plugin tool
       └─ JSON-over-stdin bridge
            ├─ OCU Planner / Executor / Reflection
            │    └─ .openclaw/plans.db
            └─ OCU cited knowledge retrieval
                 └─ .openclaw/knowledge.db
```

OpenClaw remains the channel, model-provider and plugin gateway. OCU adds a
persisted DAG planning and execution kernel. Neither project is copied into
the other.

## Installed local components

- OpenClaw Gateway: `http://127.0.0.1:18789`
- OpenClaw agent: `main`
- OCU repository: `E:\Projects\OpenClaw-Ultimate`
- OpenClaw plugin source: `integrations/openclaw-plugin`
- OpenClaw tools: `ocu_plan`, `ocu_knowledge`
- OCU plan database: `.openclaw/plans.db`

The OpenClaw plugin is linked to the repository. Changes to the plugin source
therefore become active after a safe Gateway restart.

## OCU to OpenClaw

Check the connection:

```powershell
uv run ocu openclaw status
```

Delegate a task to the existing OpenClaw Agent:

```powershell
uv run ocu openclaw ask "Summarize the current project status."
```

The adapter writes the message to a temporary UTF-8 file and invokes the
official OpenClaw CLI without a shell. The Gateway token remains in
OpenClaw's own configuration and is never copied into OCU.

## OpenClaw to OCU

The `ocu_plan` plugin tool accepts these actions:

- `status`
- `plan_create`
- `plan_show`
- `plan_run`
- `plan_reflect`

The `ocu_knowledge` tool accepts:

- `knowledge_status`
- `knowledge_search`

Search results include the indexed relative path and source line, so OpenClaw
can cite the local document instead of returning an unattributed memory.

`plan_create` and `plan_run` use OCU's existing local model and tool settings.
The Python bridge disables OCU's `ask_openclaw` tool for calls that originated
inside OpenClaw. This recursion guard prevents:

```text
OpenClaw → OCU → OpenClaw → OCU → ...
```

## Installation and repair

Run the idempotent installer from the repository root:

```powershell
.\scripts\install_openclaw_integration.ps1
```

The installer:

1. verifies `openclaw` and `uv`;
2. backs up `~\.openclaw\openclaw.json`;
3. links the local plugin when needed;
4. records the OCU project root;
5. adds only `ocu_plan` to `tools.alsoAllow`;
6. validates the OpenClaw config;
7. performs a safe Gateway restart;
8. verifies the reverse OCU-to-OpenClaw connection.

Use `-SkipRestart` only when a restart will be handled separately.

## Security boundaries

- Gateway stays bound to `127.0.0.1`.
- OCU does not store the Gateway token.
- The OpenClaw tool policy adds only `ocu_plan`, not `group:plugins`.
- The plugin uses `spawn(..., shell: false)`.
- Bridge requests and responses are bounded.
- OCU Shell remains disabled unless explicitly enabled in OCU settings.
- A bridge-originated plan cannot delegate back to OpenClaw.
- Local SQLite databases stay ignored by Git.

The Gateway `/tools/invoke` endpoint carries operator-level authority and is
used only for local acceptance tests. Applications should normally use the
OpenClaw Agent or Gateway protocol rather than distribute its bearer token.

## Verified acceptance

The local integration was validated against OpenClaw `2026.7.1-2`:

1. Gateway liveness and readiness returned healthy.
2. OCU called `main` through `openclaw agent --json` with
   `ollama/qwen3:8b`.
3. The OpenClaw Agent called `ocu_plan(status)`.
4. The OpenClaw Agent called `ocu_plan(plan_create)` and a new plan appeared
   in OCU SQLite storage.
5. Gateway invoked `ocu_plan(plan_run)`.
6. OCU read `README.md`, persisted the step result, and marked the plan
   `completed`.
