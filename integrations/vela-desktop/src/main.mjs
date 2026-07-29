import { app, BrowserWindow, dialog, shell } from "electron";
import { execFile, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP_PORT = 18790;
const APP_HOST = "127.0.0.1";
const COMFY_PORT = 8188;
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, "..");
const rendererRoot = path.join(appRoot, "renderer");
const appKey = crypto.randomBytes(24).toString("hex");

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".gif": "image/gif",
  ".htm": "text/html; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".mp3": "audio/mpeg",
  ".mp4": "video/mp4",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".wav": "audio/wav",
  ".webm": "video/webm",
  ".webp": "image/webp"
};

function readOpenClawConfig() {
  const configPath = path.join(process.env.USERPROFILE ?? app.getPath("home"), ".openclaw", "openclaw.json");
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const token = config?.gateway?.auth?.token;
  const port = Number(config?.gateway?.port ?? 18789);
  if (!token || typeof token !== "string") {
    throw new Error("OpenClaw gateway token is missing.");
  }
  return { configPath, token, port };
}

function gatewayIsAvailable(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    const finish = (available) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(available);
    };
    socket.setTimeout(800);
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.once("timeout", () => finish(false));
  });
}

function startGateway() {
  const commandPath = path.join(process.env.APPDATA ?? "", "npm", "openclaw.cmd");
  const command = fs.existsSync(commandPath) ? commandPath : "openclaw";
  return new Promise((resolve) => {
    execFile(
      command,
      ["gateway", "start"],
      { shell: process.platform === "win32", timeout: 20000, windowsHide: true },
      () => resolve()
    );
  });
}

function startComfyUi() {
  const portableRoot = "C:\\AI-Apps\\ComfyUI_windows_portable";
  const pythonPath = path.join(portableRoot, "python_embeded", "python.exe");
  const mainPath = path.join(portableRoot, "ComfyUI", "main.py");
  if (!fs.existsSync(pythonPath) || !fs.existsSync(mainPath)) return false;

  const preferredOutput = "E:\\AI-Models\\Image-Generation\\Outputs";
  const outputDirectory = fs.existsSync("E:\\AI-Models\\Image-Generation")
    ? preferredOutput
    : path.join(process.env.USERPROFILE ?? app.getPath("home"), ".openclaw", "media", "comfyui");
  fs.mkdirSync(outputDirectory, { recursive: true });

  const child = spawn(
    pythonPath,
    [
      "-s",
      mainPath,
      "--windows-standalone-build",
      "--listen",
      APP_HOST,
      "--port",
      String(COMFY_PORT),
      "--output-directory",
      outputDirectory,
      "--lowvram",
      "--reserve-vram",
      "1"
    ],
    {
      cwd: path.dirname(mainPath),
      detached: true,
      stdio: "ignore",
      windowsHide: true
    }
  );
  child.unref();
  return true;
}

async function ensureComfyUi() {
  if (await gatewayIsAvailable(COMFY_PORT)) return;
  if (!startComfyUi()) return;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (await gatewayIsAvailable(COMFY_PORT)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

async function ensureGateway(port) {
  if (await gatewayIsAvailable(port)) return;
  await startGateway();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (await gatewayIsAvailable(port)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

function findOpenClawControlUi() {
  const candidates = [
    path.join(process.env.APPDATA ?? "", "npm", "node_modules", "openclaw", "dist", "control-ui"),
    path.join(process.env.USERPROFILE ?? "", "AppData", "Roaming", "npm", "node_modules", "openclaw", "dist", "control-ui")
  ];
  const root = candidates.find((candidate) => fs.existsSync(path.join(candidate, "assets")));
  if (!root) {
    throw new Error("OpenClaw Control UI runtime was not found.");
  }
  const assetName = fs
    .readdirSync(path.join(root, "assets"))
    .find((name) => /^gateway-[A-Za-z0-9_-]+\.js$/.test(name) && !name.includes("runtime") && !name.includes("scope"));
  if (!assetName) {
    throw new Error("OpenClaw Gateway browser client was not found.");
  }
  return { root, modulePath: `/vendor/assets/${assetName}` };
}

function secureHeaders(extra = {}) {
  return {
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    ...extra
  };
}

function sendJson(res, status, payload) {
  res.writeHead(status, secureHeaders({ "Content-Type": "application/json; charset=utf-8" }));
  res.end(JSON.stringify(payload));
}

function isInside(filePath, rootPath) {
  const relative = path.relative(path.resolve(rootPath), path.resolve(filePath));
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function safeStaticPath(root, requestPath) {
  const decoded = decodeURIComponent(requestPath);
  const candidate = path.resolve(root, decoded.replace(/^[/\\]+/, ""));
  return isInside(candidate, root) ? candidate : null;
}

function streamFile(req, res, filePath, cache = false) {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    sendJson(res, 404, { error: "Not found" });
    return;
  }
  const stat = fs.statSync(filePath);
  const contentType = mimeTypes[path.extname(filePath).toLowerCase()] ?? "application/octet-stream";
  const range = req.headers.range;
  if (range) {
    const match = /bytes=(\d*)-(\d*)/.exec(range);
    const start = match?.[1] ? Number(match[1]) : 0;
    const end = match?.[2] ? Number(match[2]) : stat.size - 1;
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || end >= stat.size) {
      res.writeHead(416, { "Content-Range": `bytes */${stat.size}` });
      res.end();
      return;
    }
    res.writeHead(206, {
      ...secureHeaders(),
      "Accept-Ranges": "bytes",
      "Cache-Control": cache ? "public, max-age=86400" : "no-store",
      "Content-Length": end - start + 1,
      "Content-Range": `bytes ${start}-${end}/${stat.size}`,
      "Content-Type": contentType
    });
    fs.createReadStream(filePath, { start, end }).pipe(res);
    return;
  }
  res.writeHead(200, {
    ...secureHeaders(),
    "Accept-Ranges": "bytes",
    "Cache-Control": cache ? "public, max-age=86400" : "no-store",
    "Content-Length": stat.size,
    "Content-Type": contentType
  });
  fs.createReadStream(filePath).pipe(res);
}

function requestIsAuthorized(req, url) {
  return req.headers["x-openclaw-app-key"] === appKey || url.searchParams.get("appKey") === appKey;
}

function requestComfyJson(requestPath, timeoutMs = 2500) {
  return new Promise((resolve, reject) => {
    const request = http.get(
      { host: APP_HOST, port: COMFY_PORT, path: requestPath, timeout: timeoutMs },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          try {
            resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
          } catch (error) {
            reject(error);
          }
        });
      }
    );
    request.once("timeout", () => request.destroy(new Error("ComfyUI status timed out")));
    request.once("error", reject);
  });
}

function createServer(openClaw) {
  const vendor = findOpenClawControlUi();
  const allowedMediaExtensions = new Set([
    ".bmp", ".gif", ".jpeg", ".jpg", ".mp3", ".mp4", ".pdf", ".png", ".wav", ".webm", ".webp"
  ]);
  const allowedMediaRoots = [
    path.join(process.env.USERPROFILE ?? app.getPath("home"), ".openclaw"),
    "C:\\AI-Apps",
    "E:\\AI-Models\\Image-Generation"
  ].filter((candidate) => fs.existsSync(candidate));

  return http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", `http://${APP_HOST}:${APP_PORT}`);
      if (url.pathname === "/api/bootstrap") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        sendJson(res, 200, {
          gatewayModuleUrl: vendor.modulePath,
          gatewayUrl: `ws://127.0.0.1:${openClaw.port}`,
          token: openClaw.token,
          version: app.getVersion()
        });
        return;
      }

      if (url.pathname === "/api/image-status") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        try {
          const queue = await requestComfyJson("/queue");
          const running = Array.isArray(queue?.queue_running) ? queue.queue_running : [];
          const pending = Array.isArray(queue?.queue_pending) ? queue.queue_pending : [];
          sendJson(res, 200, {
            online: true,
            running: running.length,
            pending: pending.length,
            runningPromptId: running[0]?.[1] ?? "",
            pendingPromptId: pending[0]?.[1] ?? ""
          });
        } catch {
          sendJson(res, 200, { online: false, running: 0, pending: 0 });
        }
        return;
      }

      if (url.pathname === "/media") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const rawPath = url.searchParams.get("path") ?? "";
        const resolved = path.resolve(rawPath);
        const extension = path.extname(resolved).toLowerCase();
        if (
          !path.isAbsolute(rawPath) ||
          !allowedMediaExtensions.has(extension) ||
          !allowedMediaRoots.some((root) => isInside(resolved, root))
        ) {
          sendJson(res, 403, { error: "Media path is not allowed" });
          return;
        }
        streamFile(req, res, resolved);
        return;
      }

      if (url.pathname.startsWith("/vendor/")) {
        const vendorPath = safeStaticPath(vendor.root, url.pathname.slice("/vendor/".length));
        if (!vendorPath) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        streamFile(req, res, vendorPath, true);
        return;
      }

      if (url.pathname === "/deps/marked.js") {
        streamFile(req, res, path.join(appRoot, "node_modules", "marked", "lib", "marked.esm.js"), true);
        return;
      }
      if (url.pathname === "/deps/purify.js") {
        streamFile(req, res, path.join(appRoot, "node_modules", "dompurify", "dist", "purify.es.mjs"), true);
        return;
      }

      const requestPath = url.pathname === "/" ? "index.html" : url.pathname;
      const staticPath = safeStaticPath(rendererRoot, requestPath);
      if (!staticPath) {
        sendJson(res, 403, { error: "Forbidden" });
        return;
      }
      if (path.extname(staticPath).toLowerCase() === ".html") {
        res.setHeader(
          "Content-Security-Policy",
          [
            "default-src 'self'",
            "connect-src 'self' ws://127.0.0.1:* http://127.0.0.1:*",
            "img-src 'self' data: blob: https: http:",
            "media-src 'self' data: blob: https: http:",
            "style-src 'self' 'unsafe-inline'",
            "script-src 'self'"
          ].join("; ")
        );
      }
      streamFile(req, res, staticPath, true);
    } catch (error) {
      sendJson(res, 500, { error: error instanceof Error ? error.message : String(error) });
    }
  });
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1380,
    height: 900,
    minWidth: 980,
    minHeight: 650,
    show: false,
    backgroundColor: "#080b12",
    icon: path.join(appRoot, "build", "vela-icon.ico"),
    title: "VELA",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#080b12",
      symbolColor: "#dce9ff",
      height: 42
    },
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  const localOrigin = `http://${APP_HOST}:${APP_PORT}`;
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(localOrigin)) {
      return { action: "allow" };
    }
    void shell.openExternal(url);
    return { action: "deny" };
  });
  window.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(localOrigin)) {
      event.preventDefault();
      void shell.openExternal(url);
    }
  });
  window.once("ready-to-show", () => window.show());
  void window.loadURL(`${localOrigin}/?appKey=${appKey}`);
  return window;
}

let server;

app.setAppUserModelId("local.vela.desktop");

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const window = BrowserWindow.getAllWindows()[0];
    if (window) {
      if (window.isMinimized()) window.restore();
      if (!window.isVisible()) window.show();
      window.focus();
    }
  });

  app.whenReady().then(async () => {
    try {
      const openClaw = readOpenClawConfig();
      await ensureGateway(openClaw.port);
      void ensureComfyUi();
      server = createServer(openClaw);
      server.on("error", (error) => {
        console.error(error);
        dialog.showErrorBox("VELA", "本地应用端口被占用，请关闭旧的 VELA 窗口后重试。");
        app.quit();
      });
      server.listen(APP_PORT, APP_HOST, () => createWindow());
    } catch (error) {
      dialog.showErrorBox(
        "VELA",
        `无法启动本地应用：${error instanceof Error ? error.message : String(error)}`
      );
      app.quit();
    }
  });

  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", () => server?.close());
}
