import { app, BrowserWindow, dialog, shell } from "electron";
import { execFile, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const APP_PORT = 18790;
const APP_HOST = "127.0.0.1";
const VELA_RELEASE = "1.8.0";
const COMFY_PORT = 8188;
const OCU_PORT = 8765;
const OCU_PROJECT_ROOT = process.env.OCU_PROJECT_ROOT ?? "E:\\Projects\\OpenClaw-Ultimate";
const COMFY_INPUT_ROOT = "C:\\AI-Apps\\ComfyUI_windows_portable\\ComfyUI\\input";
const COMFY_UPSCALE_ROOT = "C:\\AI-Apps\\ComfyUI_windows_portable\\ComfyUI\\models\\upscale_models";
const COMFY_OUTPUT_ROOT = fs.existsSync("E:\\AI-Models\\Image-Generation")
  ? "E:\\AI-Models\\Image-Generation\\Outputs"
  : path.join(process.env.USERPROFILE ?? os.homedir(), ".openclaw", "media", "comfyui");
const CHARACTER_MEMORY_ROOT = "E:\\AI-Models\\Image-Generation\\Character-Memory";
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

function modelCatalog(config) {
  const configured = config?.agents?.defaults?.models ?? {};
  const primary = String(config?.agents?.defaults?.model?.primary ?? "");
  const fallbackIds = Array.isArray(config?.agents?.defaults?.model?.fallbacks)
    ? config.agents.defaults.model.fallbacks.map(String)
    : [];
  const ids = [...new Set([
    primary,
    ...fallbackIds,
    ...Object.keys(configured)
  ])].filter((id) => id && !/(?:embedding|embed)/i.test(id));
  const items = ids.map((id) => {
    const alias = configured[id]?.alias;
    const short = id.includes("/") ? id.split("/").slice(1).join("/") : id;
    const provider = id.startsWith("ollama/") ? "本地" : id.startsWith("deepseek/") ? "DeepSeek" : id.split("/")[0];
    return { id, label: alias ? `${alias} · ${short}` : `${provider} · ${short}` };
  });
  return { primary, items };
}

function openClawCommand() {
  const commandPath = path.join(process.env.APPDATA ?? "", "npm", "openclaw.cmd");
  return fs.existsSync(commandPath) ? commandPath : "openclaw";
}

function setOpenClawModel(model) {
  return new Promise((resolve, reject) => {
    execFile(
      openClawCommand(),
      ["models", "set", model],
      { shell: process.platform === "win32", timeout: 20000, windowsHide: true },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(String(stderr || stdout || error.message).trim()));
          return;
        }
        resolve(String(stdout ?? "").trim());
      }
    );
  });
}

function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 40 * 1024 * 1024) {
        req.destroy(new Error("Request body is too large"));
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function readComfyProfile(config) {
  const raw = config?.plugins?.entries?.comfy?.config;
  const image = raw?.image;
  if (!raw || !image) throw new Error("ComfyUI image profile is not configured.");
  return {
    baseUrl: String(raw.baseUrl ?? "http://127.0.0.1:8188").replace(/\/$/, ""),
    workflowPath: String(image.workflowPath),
    referenceWorkflowPath: String(image.referenceWorkflowPath ?? "C:\\AI-Apps\\OpenClaw-Workflows\\animagine-reference-api.json"),
    fluxWorkflowPath: String(image.fluxWorkflowPath ?? path.join(appRoot, "workflows", "flux2-klein-text-api.json")),
    fluxReferenceWorkflowPath: String(image.fluxReferenceWorkflowPath ?? path.join(appRoot, "workflows", "flux2-klein-reference-api.json")),
    promptNodeId: String(image.promptNodeId),
    promptInputName: String(image.promptInputName),
    outputNodeId: String(image.outputNodeId),
    fluxOutputNodeId: String(image.fluxOutputNodeId ?? "12"),
    referenceImageNodeId: String(image.referenceImageNodeId ?? "12"),
    pollIntervalMs: Number(image.pollIntervalMs ?? 1000),
    timeoutMs: Number(image.timeoutMs ?? 600000)
  };
}

function imageRoute(prompt, settings = {}) {
  const style = String(settings?.style ?? "auto").toLowerCase();
  const value = String(prompt ?? "").toLowerCase();
  if (style === "anime" || style === "illustration" || /(动漫|二次元|国漫|有兽焉|插画|拟人|兽人|anime|manga|anthropomorphic|cartoon)/i.test(value)) {
    return "anime";
  }
  if (style === "photo" || style === "natural" || /(写实|真实|摄影|照片|野生动物|photoreal|realistic|wildlife|portrait)/i.test(value)) {
    return "realistic";
  }
  return "anime";
}

function knownCharacterFacts(prompt) {
  const value = String(prompt ?? "");
  if (/(辟邪|bixie|pixiu)/i.test(value)) {
    return "Identity lock: Pixiu/Pixie from 有兽焉 (Fabulous Beasts), one small fluffy white canine-like mythical beast, red facial and body markings, red tail, red plum-blossom hindquarter markings, chartreuse-to-lime gradient eyes, two bronze back-to-back horns between the ears, notched left ear, deadpan expression. Do not turn it into a generic lucky mascot, lion, fox, cat, or dragon.";
  }
  if (/(天禄|tianlu)/i.test(value)) {
    return "Identity lock: Tianlu from 有兽焉 (Fabulous Beasts); preserve the exact reference silhouette, coat pattern, facial markings, eye colors, horns, ears, tail, and body proportions. Do not substitute another character.";
  }
  return "";
}

function referenceLockPrompt(prompt, visualSpec = "") {
  return [
    "REFERENCE-LOCKED CHARACTER EDIT.",
    "Reference image is authoritative for identity. Preserve the exact silhouette, facial geometry, proportions, palette, line weight, rendering style, and signature markings.",
    "Change only the requested pose, expression, action, camera, clothing, or background.",
    "Exactly one main subject. No companion, duplicate, clone, character sheet, collage, or generic redesign.",
    knownCharacterFacts(prompt),
    visualSpec ? `Vision inspection of the reference: ${visualSpec}` : "",
    String(prompt ?? "").trim(),
    "Do not beautify, chibify, modernize, add decorative detail, or replace the character with a namesake."
  ].filter(Boolean).join(" ");
}

function routedImagePrompt(prompt, route, visualSpec = "") {
  const cleaned = String(prompt ?? "").trim();
  if (route === "realistic") {
    return `${cleaned}, photorealistic, natural lighting, realistic material and skin or fur detail, professional photography, sharp subject, no text, no watermark`;
  }
  return `${referenceLockPrompt(cleaned, visualSpec)}, masterpiece, best quality, anime illustration, clean lineart, expressive character design, cel shading, vivid but coherent colors, no text, no watermark`;
}

function routedFluxPrompt(prompt, visualSpec = "") {
  const cleaned = String(prompt ?? "").trim();
  return `${referenceLockPrompt(cleaned, visualSpec)} High-quality concept illustration, coherent composition, clear subject silhouette, expressive pose, refined materials, controlled lighting, no text, no watermark.`;
}

function imageEngine(settings = {}) {
  const requested = String(settings?.engine ?? "anime").toLowerCase();
  if (["ssd1b", "ssd-1b", "fast", "sdxl"].includes(requested)) return "ssd1b";
  if (["realistic", "photo", "portrait", "juggernaut"].includes(requested)) return "realistic";
  return requested === "flux" || requested === "flux2" ? "flux2" : "anime";
}

function imageDimensions(settings = {}) {
  const dimensions = {
    square: [768, 768],
    landscape: [768, 432],
    portrait: [432, 768],
    classic: [768, 576],
    vertical: [576, 768],
    photo: [768, 512]
  };
  const [width, height] = dimensions[String(settings?.aspect ?? "landscape")] ?? dimensions.landscape;
  return { width, height };
}

function imageOutputDimensions(settings = {}) {
  const dimensions = {
    square: [3840, 3840],
    landscape: [3840, 2160],
    portrait: [2160, 3840],
    classic: [3840, 2880],
    vertical: [2880, 3840],
    photo: [3840, 2560]
  };
  const [width, height] = dimensions[String(settings?.aspect ?? "landscape")] ?? dimensions.landscape;
  return { width, height };
}

function imageSteps(settings = {}, engine = "anime") {
  const values = engine === "flux2"
    ? { standard: 5, high: 8, ultra: 12 }
    : engine === "ssd1b"
      ? { standard: 6, high: 10, ultra: 14 }
    : { standard: 10, high: 22, ultra: 30 };
  return values[String(settings?.quality ?? "high")] ?? values.high;
}

function decodeHtml(value) {
  return String(value ?? "")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function isImageUrl(value) {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") && !/\.(?:svg|gif)(?:$|\?)/i.test(url.pathname);
  } catch {
    return false;
  }
}

async function searchBingImageCandidates(query) {
  const searchUrl = `https://www.bing.com/images/search?q=${encodeURIComponent(query)}&form=HDRSC2`;
  const response = await fetch(searchUrl, {
    headers: {
      "User-Agent": "Mozilla/5.0 VELA/1.0",
      Accept: "text/html,application/xhtml+xml"
    },
    signal: AbortSignal.timeout(12000)
  });
  if (!response.ok) throw new Error(`Reference image search failed (${response.status}).`);
  const html = await response.text();
  const candidates = [];
  const patterns = [
    /murl(?:&quot;|"):\s*(?:&quot;|")(.*?)(?:&quot;|")/g,
    /"murl":"(.*?)"/g
  ];
  for (const pattern of patterns) {
    for (const match of html.matchAll(pattern)) {
      const url = decodeHtml(match[1]).replace(/\\u002f/g, "/");
      if (isImageUrl(url) && !candidates.includes(url)) candidates.push(url);
      if (candidates.length >= 8) break;
    }
    if (candidates.length >= 8) break;
  }
  return candidates;
}

async function searchReferenceImage(prompt) {
  const cleaned = String(prompt).trim().slice(0, 180);
  const queries = [
    `"${cleaned}" official character sheet reference illustration`,
    `${cleaned} 角色设定图 官方 立绘 正面`,
    `${cleaned} character design sheet full body reference`,
    `${cleaned} site:baike.baidu.com OR site:baike.baidu.com 角色图`,
    `${cleaned} site:pixiv.net OR site:weibo.com 角色设定`,
    `${cleaned} site:bilibili.com OR site:lofter.com 官方参考图`
  ];
  const batches = await Promise.allSettled(queries.map(searchBingImageCandidates));
  const candidates = [...new Set(batches.flatMap((batch) => batch.status === "fulfilled" ? batch.value : []))];
  if (!candidates.length) throw new Error("No usable reference image was found.");
  const terms = String(prompt).toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((term) => term.length > 1);
  return candidates.sort((left, right) => {
    const score = (value) => terms.reduce((total, term) => total + (value.toLowerCase().includes(term) ? 3 : 0), 0);
    return score(right) - score(left);
  });
}

async function availableOllamaVisionModel() {
  try {
    const response = await fetch("http://127.0.0.1:11434/api/tags", { signal: AbortSignal.timeout(2500) });
    if (!response.ok) return "";
    const models = await response.json();
    const names = Array.isArray(models?.models) ? models.models.map((item) => String(item?.name ?? "")) : [];
    return names.find((name) => /^qwen2\.5vl:3b$/i.test(name))
      ?? names.find((name) => /^qwen3-vl:8b$/i.test(name))
      ?? names.find((name) => /^moondream(?::|$)/i.test(name))
      ?? "";
  } catch {
    return "";
  }
}

async function inspectReferenceImage(localPath, prompt) {
  const model = await availableOllamaVisionModel();
  if (!model || !localPath || !fs.existsSync(localPath)) return "";
  const stat = fs.statSync(localPath);
  if (!stat.isFile() || stat.size > 12 * 1024 * 1024) return "";
  const image = fs.readFileSync(localPath).toString("base64");
  const response = await fetch("http://127.0.0.1:11434/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(60000),
    body: JSON.stringify({
      model,
      keep_alive: 0,
      stream: false,
      messages: [{
        role: "user",
        content: `Inspect this character reference for an image generator. Identify only stable visual identity traits: species, silhouette, face shape, eye colors and gradient, horns/ears, fur or hair colors, markings, tail, costume, line style, and distinctive asymmetry. Do not invent a name. Keep it under 180 words. The requested subject is: ${String(prompt).slice(0, 180)}`,
        images: [image]
      }]
    })
  });
  if (!response.ok) throw new Error(`Vision inspection failed (${response.status}).`);
  const payload = await response.json();
  return String(payload?.message?.content ?? "").replace(/\s+/g, " ").trim().slice(0, 1200);
}

function memoryIndexPath() {
  return path.join(CHARACTER_MEMORY_ROOT, "index.json");
}

function readCharacterMemory() {
  try {
    const parsed = JSON.parse(fs.readFileSync(memoryIndexPath(), "utf8"));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizedMemoryPrompt(prompt) {
  return String(prompt ?? "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 240);
}

function findCharacterMemory(prompt) {
  const normalized = normalizedMemoryPrompt(prompt);
  if (!normalized) return null;
  return readCharacterMemory()
    .filter((item) => item?.prompt && item?.path && fs.existsSync(item.path))
    .sort((left, right) => Number(right.updatedAt ?? 0) - Number(left.updatedAt ?? 0))
    .find((item) => normalized.includes(String(item.prompt).slice(0, 100)) || String(item.prompt).includes(normalized.slice(0, 100))) ?? null;
}

function findKnownReference(prompt) {
  const value = String(prompt ?? "");
  const known = [
    {
      pattern: /(辟邪|bixie|pixiu)/i,
      path: path.join(COMFY_INPUT_ROOT, "bixie_ref.png")
    },
    {
      pattern: /(天禄|tianlu)/i,
      path: path.join(COMFY_INPUT_ROOT, "tianlu_ref.png")
    }
  ];
  return known.find((item) => item.pattern.test(value) && fs.existsSync(item.path)) ?? null;
}

function saveCharacterMemory(prompt, sourcePath) {
  if (!sourcePath || !fs.existsSync(sourcePath)) return null;
  fs.mkdirSync(CHARACTER_MEMORY_ROOT, { recursive: true });
  const digest = crypto.createHash("sha256").update(normalizedMemoryPrompt(prompt)).digest("hex").slice(0, 20);
  const extension = path.extname(sourcePath).toLowerCase() === ".png" ? ".png" : ".jpg";
  const destination = path.join(CHARACTER_MEMORY_ROOT, `${digest}${extension}`);
  fs.copyFileSync(sourcePath, destination);
  const entries = readCharacterMemory().filter((item) => item?.path !== destination);
  entries.push({
    prompt: normalizedMemoryPrompt(prompt),
    path: destination,
    updatedAt: Date.now()
  });
  fs.writeFileSync(memoryIndexPath(), JSON.stringify(entries.slice(-100), null, 2), "utf8");
  return destination;
}

async function downloadReferenceImage(url, tempDirectory) {
  const response = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 VELA/1.0", Accept: "image/avif,image/webp,image/png,image/jpeg,image/*" },
    signal: AbortSignal.timeout(15000)
  });
  if (!response.ok) throw new Error(`Reference image download failed (${response.status}).`);
  const contentType = String(response.headers.get("content-type") ?? "").toLowerCase();
  if (!contentType.startsWith("image/")) throw new Error("Reference result is not an image.");
  const contentLength = Number(response.headers.get("content-length") ?? 0);
  if (contentLength > 12 * 1024 * 1024) throw new Error("Reference image is too large.");
  const buffer = Buffer.from(await response.arrayBuffer());
  if (!buffer.length || buffer.length > 12 * 1024 * 1024) throw new Error("Reference image size is invalid.");
  const extension = contentType.includes("png") ? ".png" : ".jpg";
  const filePath = path.join(tempDirectory, `reference-${crypto.randomUUID()}${extension}`);
  fs.writeFileSync(filePath, buffer);
  return filePath;
}

async function uploadReferenceImage(baseUrl, filePath) {
  const form = new FormData();
  form.append("image", new Blob([fs.readFileSync(filePath)], { type: "image/png" }), path.basename(filePath));
  form.append("overwrite", "true");
  const response = await fetch(`${baseUrl}/upload/image`, { method: "POST", body: form });
  if (!response.ok) throw new Error(`ComfyUI reference upload failed (${response.status}).`);
  const payload = await response.json();
  const name = String(payload?.name ?? "");
  if (!name) throw new Error("ComfyUI did not return an uploaded reference filename.");
  return name;
}

function removeUploadedReference(uploadedName) {
  const inputRoot = path.resolve(COMFY_INPUT_ROOT);
  const candidate = path.resolve(inputRoot, uploadedName);
  if (!isInside(candidate, inputRoot)) return;
  if (fs.existsSync(candidate)) fs.rmSync(candidate, { force: true });
}

async function createReferenceContext(profile, prompt, attachments = [], requiredWorkflowPath = profile.referenceWorkflowPath) {
  if (!fs.existsSync(requiredWorkflowPath)) throw new Error("Reference workflow is not installed.");
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "vela-reference-"));
  let uploadedName = "";
  try {
    let localPath;
    let source = "search";
    const attachment = attachments.find((item) => item?.type === "image" && item?.content);
    if (attachment) {
      const mime = String(attachment.mimeType ?? "image/png").split(";", 1)[0];
      const extension = mime.includes("jpeg") || mime.includes("jpg") ? ".jpg" : ".png";
      localPath = path.join(tempDirectory, `user-reference${extension}`);
      fs.writeFileSync(localPath, Buffer.from(String(attachment.content), "base64"));
      source = "user";
    }
    const known = localPath ? null : findKnownReference(prompt);
    if (known) {
      localPath = path.join(tempDirectory, `known-reference${path.extname(known.path) || ".png"}`);
      fs.copyFileSync(known.path, localPath);
      source = "known";
    }
    const memory = localPath ? null : findCharacterMemory(prompt);
    if (memory) {
      localPath = path.join(tempDirectory, `memory-reference${path.extname(memory.path) || ".png"}`);
      fs.copyFileSync(memory.path, localPath);
      source = "memory";
    }
    const candidates = localPath ? [] : await searchReferenceImage(prompt);
    let lastError;
    for (const candidate of candidates.slice(0, 5)) {
      try {
        localPath = await downloadReferenceImage(candidate, tempDirectory);
        break;
      } catch (error) {
        lastError = error;
      }
    }
    if (!localPath) throw lastError ?? new Error("No downloadable reference image was found.");
    uploadedName = await uploadReferenceImage(profile.baseUrl, localPath);
    let visualSpec = "";
    try {
      visualSpec = await inspectReferenceImage(localPath, prompt);
    } catch (error) {
      console.warn(`[VELA] Vision inspection unavailable: ${error instanceof Error ? error.message : String(error)}`);
    }
    return { uploadedName, tempDirectory, localPath, source, visualSpec };
  } catch (error) {
    fs.rmSync(tempDirectory, { recursive: true, force: true });
    throw error;
  }
}

function comfyViewUrl(profile, item) {
  const query = new URLSearchParams({
    filename: String(item.filename),
    subfolder: String(item.subfolder ?? ""),
    type: String(item.type ?? "output")
  });
  return `${profile.baseUrl}/view?${query.toString()}`;
}

function comfyOutputPath(item) {
  if (String(item.type ?? "output") !== "output") return null;
  const candidate = path.resolve(
    COMFY_OUTPUT_ROOT,
    String(item.subfolder ?? ""),
    String(item.filename ?? "")
  );
  if (!isInside(candidate, COMFY_OUTPUT_ROOT) || !fs.existsSync(candidate)) return null;
  return candidate;
}

async function downloadComfyImage(profile, item, tempDirectory) {
  const response = await fetch(comfyViewUrl(profile, item), { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`ComfyUI output download failed (${response.status}).`);
  const filePath = path.join(tempDirectory, `generated-${crypto.randomUUID()}.png`);
  fs.writeFileSync(filePath, Buffer.from(await response.arrayBuffer()));
  return filePath;
}

async function upscaleGeneratedOutputs(profile, images, settings, route) {
  const modelName = route === "anime" ? "RealESRGAN_x4plus_anime_6B.pth" : "RealESRGAN_x4plus.pth";
  const modelPath = path.join(COMFY_UPSCALE_ROOT, modelName);
  const targets = imageOutputDimensions(settings);
  if (!fs.existsSync(modelPath) || !images.length) {
    return { images, ...targets, resolution: "base", upscaled: false };
  }

  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "vela-upscale-"));
  const uploadedNames = [];
  try {
    throwIfImageCancelled();
    const resultImages = [];
    for (const source of images) {
      const sourcePath = await downloadComfyImage(profile, source, tempDirectory);
      const uploadedName = await uploadReferenceImage(profile.baseUrl, sourcePath);
      uploadedNames.push(uploadedName);
      const workflow = {
        "1": {
          inputs: { image: uploadedName },
          class_type: "LoadImage"
        },
        "2": {
          inputs: { model_name: modelName },
          class_type: "UpscaleModelLoader"
        },
        "3": {
          inputs: { upscale_model: ["2", 0], image: ["1", 0] },
          class_type: "ImageUpscaleWithModel"
        },
        "4": {
          inputs: {
            image: ["3", 0],
            upscale_method: "lanczos",
            width: targets.width,
            height: targets.height,
            crop: "disabled"
          },
          class_type: "ImageScale"
        },
        "5": {
          inputs: { filename_prefix: "VELA-4K", images: ["4", 0] },
          class_type: "SaveImage"
        }
      };
      const queued = await fetch(`${profile.baseUrl}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: workflow, client_id: `vela-upscale-${crypto.randomUUID()}` })
      });
      if (!queued.ok) throw new Error(`ComfyUI upscale queue failed (${queued.status}).`);
      const promptId = String((await queued.json())?.prompt_id ?? "");
      if (!promptId) throw new Error("ComfyUI did not return an upscale prompt id.");
      if (activeImageJob) {
        activeImageJob.promptId = promptId;
        activeImageJob.phase = "upscaling";
        throwIfImageCancelled(activeImageJob);
      }
      const deadline = Date.now() + profile.timeoutMs;
      while (Date.now() < deadline) {
        throwIfImageCancelled(activeImageJob);
        const history = await fetch(`${profile.baseUrl}/history/${encodeURIComponent(promptId)}`);
        if (history.ok) {
          const record = (await history.json())?.[promptId];
          const output = record?.outputs?.["5"]?.images;
          if (Array.isArray(output) && output.length) {
            resultImages.push(...output.filter((item) => item?.filename));
            break;
          }
          if (record?.status?.status_str === "error") throw new Error("ComfyUI reported an upscale error.");
        }
        await new Promise((resolve) => setTimeout(resolve, Math.max(300, profile.pollIntervalMs)));
      }
      if (!resultImages.length) throw new Error("ComfyUI upscale timed out.");
    }
    return { images: resultImages, ...targets, resolution: "4K", upscaled: true };
  } finally {
    uploadedNames.forEach(removeUploadedReference);
    fs.rmSync(tempDirectory, { recursive: true, force: true });
  }
}

function throwIfImageCancelled(job = activeImageJob) {
  if (job?.cancelled) throw new Error("Image generation cancelled.");
}

async function interruptActiveImageJob() {
  if (!activeImageJob) return false;
  activeImageJob.cancelled = true;
  try {
    const profile = activeImageJob.baseUrl;
    await fetch(`${profile}/interrupt`, { method: "POST", signal: AbortSignal.timeout(2500) });
  } catch {
    // The local job is still marked cancelled; ComfyUI may already have finished.
  }
  return true;
}

async function generateComfyImage(config, prompt, settings = {}, attachments = []) {
  const imageJob = { promptId: "", phase: "preparing", cancelled: false, baseUrl: "" };
  activeImageJob = imageJob;
  const profile = readComfyProfile(config);
  imageJob.baseUrl = profile.baseUrl;
  const requestedEngine = imageEngine(settings);
  const engine = requestedEngine === "anime" && /(有兽焉|辟邪|bixie|pixiu|天禄|tianlu)/i.test(prompt)
    ? "flux2"
    : requestedEngine;
  const hasUserReference = attachments.some((item) => item?.type === "image" && item?.content);
  const hasKnownReference = Boolean(findKnownReference(prompt));
  const hasMemoryReference = Boolean(findCharacterMemory(prompt));
  const referenceWorkflowPath = engine === "flux2" ? profile.fluxReferenceWorkflowPath : profile.referenceWorkflowPath;
  const useReference = ["anime", "flux2"].includes(engine) && settings?.reference !== "off" && settings?.referenceSearch !== false && Boolean(
    hasUserReference || hasKnownReference || hasMemoryReference || settings?.referenceSearch || settings?.reference === "strict" || /(有兽焉|角色|人物|陌生角色|同人|ip-adapter|reference|character|角色设定|辟邪|bixie|pixiu|天禄|tianlu)/i.test(prompt)
  );
  let referenceContext;
  let uploadedReferenceName = "";
  try {
    throwIfImageCancelled(imageJob);
    if (useReference && fs.existsSync(referenceWorkflowPath)) {
      imageJob.phase = "reference";
      referenceContext = await createReferenceContext(profile, prompt, attachments, referenceWorkflowPath);
      uploadedReferenceName = referenceContext.uploadedName;
    }
  } catch (error) {
    if (imageJob.cancelled) throw error;
    console.warn(`[VELA] Reference search unavailable; falling back to text-only generation: ${error instanceof Error ? error.message : String(error)}`);
  }
  const workflowPath = engine === "flux2"
    ? (referenceContext ? profile.fluxReferenceWorkflowPath : profile.fluxWorkflowPath)
    : referenceContext ? profile.referenceWorkflowPath : profile.workflowPath;
  if (!fs.existsSync(workflowPath)) {
    if (activeImageJob === imageJob) activeImageJob = null;
    throw new Error(`Image workflow is missing: ${workflowPath}`);
  }
  const workflow = JSON.parse(fs.readFileSync(workflowPath, "utf8"));
  const promptNodeId = engine === "flux2" ? "4" : profile.promptNodeId;
  const promptInputName = engine === "flux2" ? "text" : profile.promptInputName;
  const node = workflow?.[promptNodeId];
  if (!node?.inputs) {
    if (activeImageJob === imageJob) activeImageJob = null;
    throw new Error(`ComfyUI prompt node ${profile.promptNodeId} is invalid.`);
  }
  const route = engine === "realistic" ? "realistic" : imageRoute(prompt, settings);
  node.inputs[promptInputName] = engine === "flux2"
    ? routedFluxPrompt(prompt, referenceContext?.visualSpec ?? "")
    : routedImagePrompt(prompt, route, referenceContext?.visualSpec ?? "");
  const { width, height } = imageDimensions(settings);
  const steps = imageSteps(settings, engine);
  if (engine === "flux2") {
    workflow["7"].inputs.steps = steps;
    workflow["7"].inputs.width = width;
    workflow["7"].inputs.height = height;
    workflow["9"].inputs.width = width;
    workflow["9"].inputs.height = height;
    workflow["8"].inputs.noise_seed = crypto.randomInt(1, 2147483647);
    workflow["12"].inputs.filename_prefix = "VELA-FLUX2";
    if (referenceContext && workflow["30"]?.inputs) {
      workflow["30"].inputs.image = uploadedReferenceName;
    }
  } else {
    if (workflow["3"]?.inputs) workflow["3"].inputs.steps = steps;
    if (workflow["5"]?.inputs) {
      workflow["5"].inputs.width = width;
      workflow["5"].inputs.height = height;
    }
  }
  const checkpointNode = workflow?.["4"];
  if (checkpointNode?.inputs) {
    checkpointNode.inputs.ckpt_name = engine === "ssd1b"
      ? "SSD-1B-A1111.safetensors"
      : route === "anime"
        ? "animagine-xl-4.0-opt.safetensors"
        : "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors";
  }
  if (referenceContext && workflow?.[profile.referenceImageNodeId]?.inputs) {
    workflow[profile.referenceImageNodeId].inputs.image = uploadedReferenceName;
    if (workflow["10"]?.inputs) {
      workflow["10"].inputs.weight = settings.reference === "strict" ? 1.0 : 0.86;
      workflow["10"].inputs.end_at = 1.0;
      workflow["10"].inputs.weight_type = "standard";
    }
  }
  try {
    throwIfImageCancelled(imageJob);
    const queued = await fetch(`${profile.baseUrl}/prompt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: workflow, client_id: `vela-${crypto.randomUUID()}` })
    });
    if (!queued.ok) throw new Error(`ComfyUI queue failed (${queued.status}).`);
    const queuedPayload = await queued.json();
    const promptId = String(queuedPayload.prompt_id ?? "");
    if (!promptId) throw new Error("ComfyUI did not return a prompt id.");
    imageJob.promptId = promptId;
    imageJob.phase = "generating";
    throwIfImageCancelled(imageJob);

    const deadline = Date.now() + profile.timeoutMs;
    while (Date.now() < deadline) {
      throwIfImageCancelled(imageJob);
      const history = await fetch(`${profile.baseUrl}/history/${encodeURIComponent(promptId)}`);
      if (history.ok) {
        const record = (await history.json())?.[promptId];
        const outputNodeId = engine === "flux2" ? profile.fluxOutputNodeId : profile.outputNodeId;
        const images = record?.outputs?.[outputNodeId]?.images;
        if (Array.isArray(images) && images.length) {
          const upscaled = await upscaleGeneratedOutputs(profile, images, settings, route);
          if (referenceContext?.source === "user" && settings?.memory !== "once") {
            saveCharacterMemory(prompt, referenceContext.localPath);
          }
          return {
            promptId,
            engine,
            route,
            referenceUsed: Boolean(referenceContext),
            referenceSource: referenceContext?.source ?? "none",
            width: upscaled.width,
            height: upscaled.height,
            resolution: upscaled.resolution,
            upscaled: upscaled.upscaled,
            outputs: upscaled.images.map((item) => {
              const localPath = comfyOutputPath(item);
              return {
                filename: String(item.filename),
                path: localPath,
                viewUrl: comfyViewUrl(profile, item)
              };
            })
          };
        }
        if (record?.status?.status_str === "error") throw new Error("ComfyUI reported a generation error.");
      }
      await new Promise((resolve) => setTimeout(resolve, Math.max(250, profile.pollIntervalMs)));
    }
    throw new Error(`ComfyUI generation timed out after ${Math.round(profile.timeoutMs / 1000)} seconds.`);
  } finally {
    if (uploadedReferenceName) removeUploadedReference(uploadedReferenceName);
    if (referenceContext?.tempDirectory) fs.rmSync(referenceContext.tempDirectory, { recursive: true, force: true });
    if (activeImageJob === imageJob) activeImageJob = null;
  }
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

  const outputDirectory = COMFY_OUTPUT_ROOT;
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
      "1",
      "--cpu-vae"
    ],
    {
      cwd: path.dirname(mainPath),
      detached: true,
      stdio: ["ignore", fs.openSync(path.join(outputDirectory, "..", "vela-comfyui.log"), "a"), fs.openSync(path.join(outputDirectory, "..", "vela-comfyui-error.log"), "a")],
      windowsHide: true
    }
  );
  child.unref();
  return true;
}

async function ensureComfyUi() {
  if (await gatewayIsAvailable(COMFY_PORT)) return true;
  if (comfyStartPromise) return comfyStartPromise;
  comfyStartPromise = (async () => {
    if (!startComfyUi()) return false;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      if (await gatewayIsAvailable(COMFY_PORT)) return true;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    return false;
  })();
  try {
    return await comfyStartPromise;
  } finally {
    comfyStartPromise = null;
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

async function readOllamaHealth() {
  try {
    const response = await fetch("http://127.0.0.1:11434/api/tags", { signal: AbortSignal.timeout(1800) });
    if (!response.ok) return { state: "offline", count: 0 };
    const payload = await response.json();
    const models = Array.isArray(payload?.models) ? payload.models : [];
    return { state: "online", count: models.length };
  } catch {
    return { state: "offline", count: 0 };
  }
}

function resourceSnapshot() {
  const totalBytes = os.totalmem();
  const freeBytes = os.freemem();
  const snapshot = {
    memoryTotalGb: Number((totalBytes / 1024 ** 3).toFixed(1)),
    memoryFreeGb: Number((freeBytes / 1024 ** 3).toFixed(1)),
    memoryPressure: freeBytes / totalBytes < 0.15,
    modelLibrary: "E:\\AI-Models",
    modelLibraryFreeGb: null
  };
  try {
    const stats = fs.statfsSync("E:\\AI-Models");
    snapshot.modelLibraryFreeGb = Number(((Number(stats.bavail) * Number(stats.bsize)) / 1024 ** 3).toFixed(1));
  } catch {
    // Disk free space is optional on older Electron runtimes.
  }
  return snapshot;
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
          version: app.getVersion(),
          release: VELA_RELEASE
        });
        return;
      }

      if (url.pathname === "/api/health" && req.method === "GET") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const [gateway, comfy, ollama, ocu] = await Promise.all([
          gatewayIsAvailable(openClaw.port),
          gatewayIsAvailable(COMFY_PORT),
          readOllamaHealth(),
          gatewayIsAvailable(OCU_PORT)
        ]);
        sendJson(res, 200, {
          ok: gateway && comfy && ollama.state === "online",
          release: VELA_RELEASE,
          services: {
            gateway: { state: gateway ? "online" : "offline", port: openClaw.port },
            comfy: { state: comfy ? "online" : "offline", port: COMFY_PORT },
            ollama: { state: ollama.state, models: ollama.count, port: 11434 },
            ocu: { state: ocu ? "online" : "offline", port: OCU_PORT }
          },
          resources: resourceSnapshot(),
          imageJob: activeImageJob
            ? { phase: activeImageJob.phase, promptId: activeImageJob.promptId, cancellable: true }
            : null
        });
        return;
      }

      if (url.pathname === "/api/models") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const config = JSON.parse(fs.readFileSync(openClaw.configPath, "utf8"));
        sendJson(res, 200, modelCatalog(config));
        return;
      }

      if (url.pathname === "/api/generate-image" && req.method === "POST") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const payload = JSON.parse(await readRequestBody(req));
        const prompt = typeof payload?.prompt === "string" ? payload.prompt.trim() : "";
        if (!prompt) {
          sendJson(res, 400, { error: "Image prompt is empty." });
          return;
        }
        if (!(await ensureComfyUi())) {
          sendJson(res, 503, { error: "ComfyUI is unavailable. Image generation was not started." });
          return;
        }
        const config = JSON.parse(fs.readFileSync(openClaw.configPath, "utf8"));
        const settings = payload?.settings && typeof payload.settings === "object" ? payload.settings : {};
        const attachments = Array.isArray(payload?.attachments) ? payload.attachments.slice(0, 2) : [];
        sendJson(res, 200, await generateComfyImage(config, prompt, settings, attachments));
        return;
      }

      if (url.pathname === "/api/image-cancel" && req.method === "POST") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        sendJson(res, 200, { ok: await interruptActiveImageJob() });
        return;
      }

      if (url.pathname === "/api/model" && req.method === "POST") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const payload = JSON.parse(await readRequestBody(req));
        const model = typeof payload?.model === "string" ? payload.model.trim() : "";
        const config = JSON.parse(fs.readFileSync(openClaw.configPath, "utf8"));
        const catalog = modelCatalog(config);
        const selected = catalog.items.find((item) => item.id === model);
        if (!selected) {
          sendJson(res, 400, { error: "Model is not configured for VELA." });
          return;
        }
        await setOpenClawModel(selected.id);
        const refreshed = JSON.parse(fs.readFileSync(openClaw.configPath, "utf8"));
        sendJson(res, 200, { primary: modelCatalog(refreshed).primary, label: selected.label });
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
            pendingPromptId: pending[0]?.[1] ?? "",
            activePhase: activeImageJob?.phase ?? "",
            cancellable: Boolean(activeImageJob)
          });
        } catch {
          sendJson(res, 200, { online: false, running: 0, pending: 0 });
        }
        return;
      }

      if (url.pathname === "/api/ocu/status" && req.method === "GET") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        try {
          await ensureOcuApi();
          sendJson(res, 200, await requestOcuJson("/v1/status"));
        } catch (error) {
          sendJson(res, 503, {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
          });
        }
        return;
      }

      if (url.pathname === "/api/ocu/plans" && req.method === "GET") {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        try {
          await ensureOcuApi();
          sendJson(res, 200, await requestOcuJson("/v1/plans"));
        } catch (error) {
          sendJson(res, 503, {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
          });
        }
        return;
      }

      const ocuPlanRoute = url.pathname.match(/^\/api\/ocu\/plans\/([^/]+)(?:\/(show|reflect|run))?$/);
      if (ocuPlanRoute && (req.method === "GET" || req.method === "POST")) {
        if (!requestIsAuthorized(req, url)) {
          sendJson(res, 403, { error: "Forbidden" });
          return;
        }
        const planId = decodeURIComponent(ocuPlanRoute[1]);
        const operation = ocuPlanRoute[2] ?? "show";
        const apiPath = operation === "show"
          ? `/v1/plans/${encodeURIComponent(planId)}`
          : `/v1/plans/${encodeURIComponent(planId)}/${operation}`;
        try {
          await ensureOcuApi();
          sendJson(res, 200, await requestOcuJson(apiPath, operation === "show" ? "GET" : "POST"));
        } catch (error) {
          sendJson(res, 503, {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
          });
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
    backgroundColor: "#09090a",
    icon: path.join(appRoot, "build", "vela-icon.ico"),
    title: "VELA",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#00000000",
      symbolColor: "#737373",
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
let ocuProcess = null;
let ocuStartPromise = null;
let comfyStartPromise = null;
let activeImageJob = null;

function requestOcuJson(requestPath, method = "GET", payload = null, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const body = payload == null ? null : Buffer.from(JSON.stringify(payload), "utf8");
    const request = http.request(
      {
        host: APP_HOST,
        port: OCU_PORT,
        path: requestPath,
        method,
        timeout: timeoutMs,
        headers: body
          ? {
              "Content-Type": "application/json",
              "Content-Length": body.length
            }
          : undefined
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const raw = Buffer.concat(chunks).toString("utf8");
          let parsed;
          try {
            parsed = JSON.parse(raw);
          } catch (error) {
            reject(new Error(`OpenClaw-Ultimate API returned invalid JSON (${response.statusCode}).`));
            return;
          }
          if ((response.statusCode ?? 500) >= 400) {
            reject(new Error(parsed?.error?.message ?? `OpenClaw-Ultimate API failed (${response.statusCode}).`));
            return;
          }
          resolve(parsed);
        });
      }
    );
    request.once("timeout", () => request.destroy(new Error("OpenClaw-Ultimate API timed out")));
    request.once("error", reject);
    if (body) request.write(body);
    request.end();
  });
}

async function ensureOcuApi() {
  if (ocuStartPromise) return ocuStartPromise;
  ocuStartPromise = (async () => {
    // The full status route performs deep component checks and may exceed a
    // cold-start timeout even when the API is already listening. Prefer a
    // cheap loopback probe so desktop restarts never spawn duplicate servers.
    if (await gatewayIsAvailable(OCU_PORT)) return true;
    try {
      await requestOcuJson("/v1/status", "GET", null, 1200);
      return true;
    } catch {
      // Start the project's local API only when it is not already available.
    }

    const projectFile = path.join(OCU_PROJECT_ROOT, "pyproject.toml");
    if (!fs.existsSync(projectFile)) return false;
    if (!ocuProcess || ocuProcess.exitCode !== null) {
      try {
        const uvCandidates = [
          process.env.OCU_UV_PATH,
          path.join(process.env.USERPROFILE ?? "", ".local", "bin", "uv.exe"),
          "uv"
        ].filter(Boolean);
        const uvCommand = uvCandidates.find((candidate) => candidate === "uv" || fs.existsSync(candidate)) ?? "uv";
        ocuProcess = spawn(
          uvCommand,
          ["run", "--no-sync", "--project", OCU_PROJECT_ROOT, "ocu", "serve", "--host", APP_HOST, "--port", String(OCU_PORT)],
          {
            cwd: OCU_PROJECT_ROOT,
            windowsHide: true,
            stdio: "ignore"
          }
        );
        ocuProcess.once("error", () => {
          ocuProcess = null;
        });
        ocuProcess.once("exit", () => {
          ocuProcess = null;
        });
      } catch {
        ocuProcess = null;
        return false;
      }
    }

    const deadline = Date.now() + 12000;
    while (Date.now() < deadline) {
      try {
        await requestOcuJson("/v1/status", "GET", null, 1500);
        return true;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
    }
    return false;
  })();
  try {
    return await ocuStartPromise;
  } finally {
    ocuStartPromise = null;
  }
}

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
  app.on("before-quit", () => {
    server?.close();
    if (ocuProcess && ocuProcess.exitCode === null) ocuProcess.kill();
  });
}
