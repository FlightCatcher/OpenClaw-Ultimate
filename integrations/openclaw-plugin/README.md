# VELA plugin for OpenClaw

This local OpenClaw tool plugin exposes VELA's persisted planning runtime as
the `ocu_plan` tool and its cited local RAG index as `ocu_knowledge`.

The plugin starts the Python bridge with `uv` and exchanges JSON over stdin and
stdout. It does not copy the OpenClaw Gateway token and it disables VELA's
`ask_openclaw` delegation while executing bridge requests to prevent recursive
OpenClaw → VELA → OpenClaw loops. The legacy tool names remain unchanged for
backward compatibility.

Supported actions:

- `status`
- `plan_create`
- `plan_show`
- `plan_run`
- `plan_reflect`

Knowledge actions:

- `knowledge_status`
- `knowledge_search`
