import { spawn } from "node:child_process";
import path from "node:path";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const ACTIONS = [
  "status",
  "plan_create",
  "plan_show",
  "plan_run",
  "plan_reflect",
];
const KNOWLEDGE_ACTIONS = ["knowledge_status", "knowledge_search"];

function readConfig(value) {
  const raw = value && typeof value === "object" ? value : {};
  const projectRoot =
    typeof raw.projectRoot === "string" ? raw.projectRoot.trim() : "";
  const uvCommand =
    typeof raw.uvCommand === "string" && raw.uvCommand.trim()
      ? raw.uvCommand.trim()
      : "uv";
  const timeoutMs =
    Number.isInteger(raw.timeoutMs) &&
    raw.timeoutMs >= 1000 &&
    raw.timeoutMs <= 1_800_000
      ? raw.timeoutMs
      : 600_000;

  if (!projectRoot || !path.isAbsolute(projectRoot)) {
    throw new Error(
      "openclaw-ultimate requires an absolute plugin config projectRoot.",
    );
  }

  return { projectRoot, uvCommand, timeoutMs };
}

function runBridge(config, request) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      config.uvCommand,
      [
        "--directory",
        config.projectRoot,
        "run",
        "python",
        "-m",
        "openclaw_ultimate.bridge",
      ],
      {
        cwd: config.projectRoot,
        windowsHide: true,
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (callback) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      callback();
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(() =>
        reject(
          new Error(`OCU bridge timed out after ${config.timeoutMs} ms.`),
        ),
      );
    }, config.timeoutMs);

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      if (stdout.length > 5_000_000) {
        child.kill();
        finish(() => reject(new Error("OCU bridge output exceeded 5 MB.")));
      }
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
      if (stderr.length > 100_000) {
        stderr = stderr.slice(-100_000);
      }
    });
    child.on("error", (error) => {
      finish(() => reject(error));
    });
    child.on("close", (code) => {
      finish(() => {
        let payload;
        try {
          payload = JSON.parse(stdout);
        } catch {
          reject(
            new Error(
              `OCU bridge returned invalid JSON (exit ${code}): ${stderr.slice(
                0,
                1000,
              )}`,
            ),
          );
          return;
        }

        if (code !== 0 || payload?.ok !== true) {
          const message =
            payload?.error?.message ||
            stderr.trim().slice(0, 1000) ||
            `OCU bridge failed with exit code ${code}.`;
          reject(new Error(message));
          return;
        }

        resolve(payload);
      });
    });

    child.stdin.end(JSON.stringify(request), "utf8");
  });
}

export default definePluginEntry({
  id: "openclaw-ultimate",
  name: "OpenClaw Ultimate",
  description: "Adds OCU planning, DAG execution and reflection to OpenClaw.",
  register(api) {
    const config = readConfig(api.pluginConfig);

    api.registerTool({
      name: "ocu_plan",
      description:
        "Use the local OpenClaw Ultimate runtime to create, inspect, execute, " +
        "or reflect on persisted DAG plans. plan_run can execute OCU tools; " +
        "use it only when the user asked to run the plan.",
      parameters: {
        type: "object",
        properties: {
          action: {
            type: "string",
            enum: ACTIONS,
          },
          goal: {
            type: "string",
            description: "Required for plan_create.",
            minLength: 1,
          },
          plan_id: {
            type: "string",
            description:
              "Required for plan_show, plan_run, and plan_reflect.",
            minLength: 1,
          },
        },
        required: ["action"],
        additionalProperties: false,
      },
      async execute(_id, params) {
        const result = await runBridge(config, {
          action: params.action,
          goal: params.goal,
          plan_id: params.plan_id,
        });

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      },
    });

    api.registerTool({
      name: "ocu_knowledge",
      description:
        "Search the local OCU knowledge index and return source file and " +
        "line citations. Use knowledge_status to inspect index readiness.",
      parameters: {
        type: "object",
        properties: {
          action: {
            type: "string",
            enum: KNOWLEDGE_ACTIONS,
          },
          query: {
            type: "string",
            description: "Required for knowledge_search.",
            minLength: 1,
          },
          limit: {
            type: "integer",
            minimum: 1,
            maximum: 20,
            default: 5,
          },
        },
        required: ["action"],
        additionalProperties: false,
      },
      async execute(_id, params) {
        const result = await runBridge(config, {
          action: params.action,
          query: params.query,
          limit: params.limit,
        });

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      },
    });
  },
});
