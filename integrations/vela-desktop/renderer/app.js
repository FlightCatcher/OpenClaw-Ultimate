import { marked } from "/deps/marked.js";
import createDOMPurify from "/deps/purify.js";

const DOMPurify = createDOMPurify(window);
marked.setOptions({ breaks: true, gfm: true });

const translations = {
  zh: {
    analyzeFile: "分析文件",
    analyzeFileHint: "图片、文档或音视频",
    attach: "文件",
    connected: "已连接",
    connecting: "正在连接",
    disconnected: "连接中断",
    dropFiles: "释放以上传文件",
    fileAdded: "文件已添加",
    fileLimit: "最多添加 8 个文件，每个不超过 25 MB",
    generateImage: "生成图片",
    generateImageHint: "使用本地 ComfyUI",
    imageMode: "生图",
    imageModeActive: "生图模式已开启",
    imageAspect: "画幅",
    imageQuality: "质量",
    imageStudioHint: "动漫参考 / FLUX.2 Klein · 稳定单次生成",
    imageEngine: "引擎",
    engineAnime: "动漫参考",
    engineFast: "快速 SDXL",
    engineFlux: "FLUX.2",
    imageStudioTitle: "图像工作室",
    imageReference: "角色参考",
    imageStyle: "质感",
    localAgent: "本地智能体",
    localPrivate: "本地 · 私密",
    messagePlaceholder: "给 VELA 发消息",
    modelLabel: "模型",
    modelNote: "当前模型 · OpenClaw 执行引擎",
    modelLoading: "正在读取模型",
    modelSwitching: "正在切换模型…",
    modelSwitched: "模型已切换",
    modelSwitchFailed: "模型切换失败",
    themeLight: "切换到白天模式",
    themeDark: "切换到黑夜模式",
    themeDay: "白天",
    themeNight: "黑夜",
    controlCenter: "智能体控制中心",
    workspaceSyncing: "同步中",
    workspaceSynced: "已同步",
    workspaceOffline: "本地 API 离线",
    workspaceRefresh: "刷新",
    workspaceEmpty: "还没有已保存的计划",
    workspaceSelectPlan: "选择一个计划查看步骤、结果和失败诊断",
    workspaceStatus: "状态",
    workspaceSteps: "步骤",
    workspaceUpdated: "更新时间",
    workspaceNoDetail: "暂无执行详情",
    statusOnline: "在线",
    statusOffline: "离线",
    statusReady: "就绪",
    statusRunning: "运行中",
    statusCompleted: "已完成",
    statusFailed: "失败",
    statusPending: "等待",
    reflectionTitle: "Reflection 诊断",
    reflectionRetryable: "可恢复",
    reflectionSuggested: "建议",
    workspaceNav: "工作区",
    workspaceChat: "对话",
    workspaceTasks: "任务",
    workspacePlans: "计划",
    workspaceRuns: "运行",
    workspaceModels: "模型",
    workspaceTools: "工具",
    workspaceLive: "实时工作区",
    workspaceOpen: "展开可视化",
    workspaceClose: "收起可视化",
    flowIntent: "理解",
    flowPlan: "规划",
    flowExecute: "执行",
    flowVerify: "验证",
    metricSession: "会话",
    metricHistory: "消息",
    metricMode: "模式",
    metricReady: "就绪",
    metricWorking: "工作中",
    metricImage: "生图",
    newChat: "新对话",
    noText: "附件",
    openWeb: "联网研究",
    openWebHint: "搜索、整理与创作",
    recents: "最近",
    reconnect: "重新连接",
    sendFailed: "发送失败",
    sendHint: "Enter 发送",
    qualityHigh: "推荐 22 步",
    qualityStandard: "快速 5 步",
    qualityUltra: "极致 30 步",
    referenceHint: "上传参考图可锁定脸型、发型和服装；严格模式优先保留身份",
    textFidelity: "文字清晰",
    textAuto: "智能",
    textClear: "清晰排版",
    textNone: "无文字",
    progressPreparing: "正在理解你的需求",
    progressSemantic: "正在提取主体、场景与动作",
    progressDetail: "正在补全合理画面细节",
    progressComposition: "正在设计镜头与构图",
    progressStyle: "正在融合风格、光影与色彩",
    progressConsistency: "正在检查画面设定冲突",
    progressRouting: "正在搜索资料并选择专用模型",
    progressQueued: "已进入生成队列",
    progressGenerating: "ComfyUI 正在生成",
    progressChecking: "生成完成，正在显示图片",
    progressOffline: "本地生图引擎未连接",
    progressEstimate: "预计进度",
    referenceOff: "关闭",
    referenceSmart: "自动学习",
    referenceStrict: "严格还原",
    styleAnime: "动漫",
    styleAuto: "智能",
    styleCinematic: "电影",
    styleIllustration: "插画",
    styleNatural: "自然",
    stylePhoto: "摄影",
    styleProduct: "产品",
    subtitle: "可聊天、看图、读文件，也可以直接在对话中生成图片。",
    thinking: "VELA 正在处理",
    title: "今天想让 VELA 做什么？",
    untitled: "新对话"
  },
  en: {
    analyzeFile: "Analyze files",
    analyzeFileHint: "Images, docs, audio or video",
    attach: "Attach",
    connected: "Connected",
    connecting: "Connecting",
    disconnected: "Disconnected",
    dropFiles: "Drop files to upload",
    fileAdded: "File added",
    fileLimit: "Up to 8 files, 25 MB each",
    generateImage: "Create an image",
    generateImageHint: "Powered by local ComfyUI",
    imageMode: "Image",
    imageModeActive: "Image mode enabled",
    imageAspect: "Canvas",
    imageQuality: "Quality",
    imageStudioHint: "Anime reference / FLUX.2 Klein · Stable single generation",
    imageEngine: "Engine",
    engineAnime: "Anime reference",
    engineFast: "Fast SDXL",
    engineFlux: "FLUX.2",
    imageStudioTitle: "Image Studio",
    imageReference: "Character reference",
    imageStyle: "Texture",
    localAgent: "Local agent",
    localPrivate: "Local · Private",
    messagePlaceholder: "Message VELA",
    modelLabel: "Model",
    modelNote: "Current model · OpenClaw execution engine",
    modelLoading: "Loading models",
    modelSwitching: "Switching model…",
    modelSwitched: "Model switched",
    modelSwitchFailed: "Could not switch model",
    themeLight: "Switch to light mode",
    themeDark: "Switch to dark mode",
    themeDay: "Light",
    themeNight: "Dark",
    controlCenter: "AGENT CONTROL CENTER",
    workspaceSyncing: "Syncing",
    workspaceSynced: "Synced",
    workspaceOffline: "Local API offline",
    workspaceRefresh: "Refresh",
    workspaceEmpty: "No saved plans yet",
    workspaceSelectPlan: "Select a plan to inspect steps, results and failures",
    workspaceStatus: "Status",
    workspaceSteps: "Steps",
    workspaceUpdated: "Updated",
    workspaceNoDetail: "No execution detail yet",
    statusOnline: "Online",
    statusOffline: "Offline",
    statusReady: "Ready",
    statusRunning: "Running",
    statusCompleted: "Completed",
    statusFailed: "Failed",
    statusPending: "Pending",
    reflectionTitle: "Reflection diagnosis",
    reflectionRetryable: "Retryable",
    reflectionSuggested: "Suggested action",
    workspaceNav: "Workspace",
    workspaceChat: "Chat",
    workspaceTasks: "Tasks",
    workspacePlans: "Plans",
    workspaceRuns: "Runs",
    workspaceModels: "Models",
    workspaceTools: "Tools",
    workspaceLive: "Live workspace",
    workspaceOpen: "Open visualizer",
    workspaceClose: "Close visualizer",
    flowIntent: "Understand",
    flowPlan: "Plan",
    flowExecute: "Execute",
    flowVerify: "Verify",
    metricSession: "Session",
    metricHistory: "Messages",
    metricMode: "Mode",
    metricReady: "Ready",
    metricWorking: "Working",
    metricImage: "Image",
    newChat: "New chat",
    noText: "Attachment",
    openWeb: "Research the web",
    openWebHint: "Search, synthesize and create",
    recents: "Recent",
    reconnect: "Reconnect",
    sendFailed: "Could not send",
    sendHint: "Enter to send",
    qualityHigh: "Recommended · 22",
    qualityStandard: "Fast · 5",
    qualityUltra: "Ultra · 30",
    referenceHint: "Attach a reference to lock face, hair and outfit; strict mode favors identity",
    textFidelity: "Text fidelity",
    textAuto: "Auto",
    textClear: "Clear layout",
    textNone: "No text",
    progressPreparing: "Understanding your request",
    progressSemantic: "Extracting subject, scene and action",
    progressDetail: "Completing coherent visual details",
    progressComposition: "Designing camera and composition",
    progressStyle: "Blending style, light and color",
    progressConsistency: "Checking visual consistency",
    progressRouting: "Researching and selecting a specialist model",
    progressQueued: "Queued for generation",
    progressGenerating: "ComfyUI is generating",
    progressChecking: "Generated; displaying the image",
    progressOffline: "Local image engine is offline",
    progressEstimate: "Estimated progress",
    referenceOff: "Off",
    referenceSmart: "Learn automatically",
    referenceStrict: "Strict identity",
    styleAnime: "Anime",
    styleAuto: "Auto",
    styleCinematic: "Cinema",
    styleIllustration: "Illustration",
    styleNatural: "Natural",
    stylePhoto: "Photo",
    styleProduct: "Product",
    subtitle: "Chat, understand files and images, or create images directly in the conversation.",
    thinking: "VELA is working",
    title: "What should VELA do today?",
    untitled: "New chat"
  }
};

const els = {
  app: document.querySelector("#app"),
  attachButton: document.querySelector("#attach-button"),
  attachmentStrip: document.querySelector("#attachment-strip"),
  chatContent: document.querySelector("#chat-content"),
  chatScroll: document.querySelector("#chat-scroll"),
  chatTitle: document.querySelector("#chat-title"),
  composer: document.querySelector("#composer"),
  composerInput: document.querySelector("#composer-input"),
  connectionLabel: document.querySelector("#connection-label"),
  connectionPill: document.querySelector("#connection-pill"),
  dropOverlay: document.querySelector("#drop-overlay"),
  fileInput: document.querySelector("#file-input"),
  imageModeButton: document.querySelector("#image-mode-button"),
  imageStudio: document.querySelector("#image-studio"),
  languageButton: document.querySelector("#language-button"),
  languageLabel: document.querySelector("#language-label"),
  mediaClose: document.querySelector("#media-close"),
  mediaDialog: document.querySelector("#media-dialog"),
  mediaDialogImage: document.querySelector("#media-dialog-image"),
  modelSelect: document.querySelector("#model-select"),
  commandDeck: document.querySelector("#command-deck"),
  workspaceToggle: document.querySelector("#workspace-toggle"),
  deckStatus: document.querySelector("#deck-status"),
  deckMode: document.querySelector("#deck-mode"),
  deckSession: document.querySelector("#deck-session"),
  deckHistory: document.querySelector("#deck-history"),
  newChatButton: document.querySelector("#new-chat-button"),
  retryButton: document.querySelector("#retry-button"),
  sendButton: document.querySelector("#send-button"),
  sessionList: document.querySelector("#session-list"),
  sidebar: document.querySelector("#sidebar"),
  sidebarButton: document.querySelector("#sidebar-button"),
  stopButton: document.querySelector("#stop-button"),
  themeButton: document.querySelector("#theme-button"),
  workspaceNav: document.querySelector("#workspace-nav"),
  workspacePanel: document.querySelector("#workspace-panel"),
  workspacePanelTitle: document.querySelector("#workspace-panel-title"),
  workspacePanelSync: document.querySelector("#workspace-panel-sync"),
  workspacePanelRefresh: document.querySelector("#workspace-panel-refresh"),
  workspacePanelMetrics: document.querySelector("#workspace-panel-metrics"),
  workspacePanelList: document.querySelector("#workspace-panel-list"),
  workspacePanelDetail: document.querySelector("#workspace-panel-detail"),
  toastRegion: document.querySelector("#toast-region")
};

// Keep the live workspace in the document root so the glass panel is never
// clipped by the chat grid or its scrolling container.
if (els.commandDeck && els.commandDeck.parentElement !== document.body) {
  document.body.appendChild(els.commandDeck);
}
if (els.commandDeck) {
  Object.assign(els.commandDeck.style, {
    position: "fixed",
    top: "134px",
    left: "312px",
    right: "30px",
    height: "106px",
    minHeight: "106px",
    maxHeight: "106px",
    zIndex: "9999",
    display: "block",
    overflow: "visible",
  });
}

const query = new URLSearchParams(location.search);
const appKey = query.get("appKey") ?? "";
history.replaceState({}, "", "/");

const defaultSession = {
  key: "agent:main:openclaw-desktop",
  title: translations.zh.untitled,
  updatedAt: Date.now()
};

const defaultImageSettings = {
  aspect: "landscape",
  engine: "anime",
  quality: "high",
  reference: "smart",
  style: "auto",
  textMode: "auto"
};

const state = {
  activeRunId: null,
  attachments: [],
  bootstrap: null,
  client: null,
  connected: false,
  history: [],
  imageMode: false,
  activeImageRun: false,
  imageProgress: { value: 0, stage: "", detail: "" },
  imageQueueSeen: false,
  imageStartedAt: 0,
  imageStatusTimer: null,
  imageSettings: loadImageSettings(),
  models: { primary: "", items: [] },
  language: localStorage.getItem("openclaw.desktop.language") === "en" ? "en" : "zh",
  optimistic: null,
  pending: false,
  pollTimer: null,
  refreshForceScroll: false,
  refreshInFlight: false,
  refreshQueued: false,
  refreshTimer: null,
  renderedMessagesKey: "",
  sessions: loadSessions(),
  theme: loadTheme(),
  workspaceView: "chat",
  workspaceData: {
    loading: false,
    error: "",
    status: null,
    plans: [],
    selectedPlanId: "",
    detail: null
  },
  workspaceRefreshTimer: null
};

function loadTheme() {
  const saved = localStorage.getItem("vela.desktop.theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

let currentSessionKey =
  localStorage.getItem("openclaw.desktop.currentSession") ??
  state.sessions[0]?.key ??
  defaultSession.key;

function t(key) {
  return translations[state.language][key] ?? key;
}

function loadImageSettings() {
  try {
    const parsed = JSON.parse(localStorage.getItem("openclaw.desktop.imageSettings") ?? "{}");
    return {
      aspect: ["square", "landscape", "portrait", "classic", "vertical", "photo"].includes(parsed.aspect)
        ? parsed.aspect
        : defaultImageSettings.aspect,
      engine: ["anime", "ssd1b", "flux2"].includes(parsed.engine) ? parsed.engine : defaultImageSettings.engine,
      quality: ["standard", "high", "ultra"].includes(parsed.quality)
        ? parsed.quality
        : defaultImageSettings.quality,
      reference: ["smart", "strict", "off"].includes(parsed.reference)
        ? parsed.reference
        : defaultImageSettings.reference,
      style: ["auto", "natural", "cinematic", "photo", "anime", "illustration", "product"].includes(parsed.style)
        ? parsed.style
        : defaultImageSettings.style,
      textMode: ["auto", "clear", "none"].includes(parsed.textMode)
        ? parsed.textMode
        : defaultImageSettings.textMode
    };
  } catch {
    return { ...defaultImageSettings };
  }
}

function saveImageSettings() {
  localStorage.setItem("openclaw.desktop.imageSettings", JSON.stringify(state.imageSettings));
}

function loadSessions() {
  try {
    const parsed = JSON.parse(localStorage.getItem("openclaw.desktop.sessions") ?? "[]");
    if (Array.isArray(parsed) && parsed.length) return parsed.slice(0, 30);
  } catch {
    // Ignore malformed local state.
  }
  return [defaultSession];
}

function saveSessions() {
  state.sessions.sort((a, b) => b.updatedAt - a.updatedAt);
  localStorage.setItem("openclaw.desktop.sessions", JSON.stringify(state.sessions.slice(0, 30)));
  localStorage.setItem("openclaw.desktop.currentSession", currentSessionKey);
}

function currentSession() {
  return state.sessions.find((session) => session.key === currentSessionKey) ?? state.sessions[0];
}

function updateCurrentSession(patch) {
  const existing = currentSession();
  if (existing) {
    Object.assign(existing, patch);
  } else {
    state.sessions.unshift({ key: currentSessionKey, title: t("untitled"), updatedAt: Date.now(), ...patch });
  }
  saveSessions();
  renderSessions();
  renderHeader();
}

function newSession() {
  const key = `agent:main:desktop-${crypto.randomUUID()}`;
  state.sessions.unshift({ key, title: t("untitled"), updatedAt: Date.now() });
  currentSessionKey = key;
  state.history = [];
  state.optimistic = null;
  state.pending = false;
  state.activeRunId = null;
  saveSessions();
  renderAll(true);
  if (state.connected) void refreshHistory(true);
  requestAnimationFrame(() => els.composerInput.focus());
}

function setSession(key) {
  if (key === currentSessionKey) return;
  currentSessionKey = key;
  state.history = [];
  state.optimistic = null;
  state.pending = false;
  state.activeRunId = null;
  saveSessions();
  renderAll(true);
  if (state.connected) void refreshHistory(true);
}

function formatTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-US", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdown(text) {
  const html = marked.parse(text ?? "");
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["target", "rel"],
    FORBID_TAGS: ["iframe", "object", "embed", "form", "input", "button", "style"]
  });
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((block) => block?.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("\n\n");
}

function cleanUserText(text) {
  const studioPrompt = text.match(
    /OPENCLAW_IMAGE_STUDIO_V2[\s\S]*?PROMPT_BEGIN\r?\n([\s\S]*?)\r?\nPROMPT_END/i
  );
  if (studioPrompt) return studioPrompt[1].trim();
  return text
    .replace(
      /^(?:请使用本地生图工具生成并在当前聊天中返回图片：|Use the local image-generation tool and return the image in this chat:)\s*/i,
      ""
    )
    .trim();
}

function isHiddenMessage(message) {
  const role = message?.role;
  if (role !== "user" && role !== "assistant") return true;
  if (message?.provenance?.kind === "inter_session") return true;
  const text = contentText(message?.content);
  if (text.includes("<<<BEGIN_OPENCLAW_INTERNAL_CONTEXT>>>")) return true;
  if (role === "user" && /^A background task completed\./.test(text)) return true;
  return false;
}

function normalizeHistoryMessage(entry) {
  if (entry?.type === "message" && entry?.message) return entry.message;
  return entry;
}

function normalizePath(value) {
  return String(value ?? "")
    .trim()
    .replace(/^["']|["']$/g, "")
    .replace(/[)\]}>,.;]+$/g, "");
}

function isLocalPath(value) {
  return /^[A-Za-z]:[\\/]/.test(value) || value.startsWith("/");
}

function mediaUrl(value) {
  const normalized = normalizePath(value);
  if (/^(?:data:|blob:|https?:)/i.test(normalized)) return normalized;
  if (isLocalPath(normalized)) {
    return `/media?appKey=${encodeURIComponent(appKey)}&path=${encodeURIComponent(normalized)}`;
  }
  return normalized;
}

function mediaKind(value, mimeType = "") {
  const source = `${value} ${mimeType}`.toLowerCase();
  if (/\.(?:png|jpe?g|webp|gif|bmp)(?:$|[?#\s])/.test(source) || mimeType.startsWith("image/") || /\/view(?:\?|$)/.test(source)) return "image";
  if (/\.(?:mp4|webm)(?:$|[?#\s])/.test(source) || mimeType.startsWith("video/")) return "video";
  if (/\.(?:mp3|wav)(?:$|[?#\s])/.test(source) || mimeType.startsWith("audio/")) return "audio";
  return "file";
}

function extractMessageParts(message) {
  let text = contentText(message?.content);
  if (message?.role === "user") text = cleanUserText(text);
  const media = [];
  const files = [];
  const seen = new Set();
  const hasMediaDirective = /(?:^|\n)\s*MEDIA:\s*(?:[A-Za-z]:|\/)/i.test(text);
  const hasNativeImage =
    hasMediaDirective
    ||
    (Array.isArray(message?.content)
      && message.content.some((block) => block?.type === "image"))
    || (typeof message?.mediaUrl === "string" && mediaKind(message.mediaUrl) === "image")
    || (Array.isArray(message?.mediaUrls)
      && message.mediaUrls.some((value) => mediaKind(value) === "image"));

  const add = (raw, mimeType = "", label = "") => {
    const value = normalizePath(raw);
    if (!value || seen.has(value)) return;
    seen.add(value);
    const kind = mediaKind(value, mimeType);
    const item = { kind, label: label || value.split(/[\\/]/).pop() || t("noText"), mimeType, raw: value, src: mediaUrl(value) };
    if (kind === "image" || kind === "video" || kind === "audio") media.push(item);
    else files.push(item);
  };

  const mediaLinePattern = /(?:^|\n)\s*MEDIA:\s*((?:https?:\/\/|[A-Za-z]:|\/)[^\r\n]+)/gi;
  text = text.replace(mediaLinePattern, (_match, value) => {
    add(value);
    return "\n";
  });

  const markdownImagePattern = /!\[([^\]]*)\]\(([^)]+)\)/g;
  text = text.replace(markdownImagePattern, (_match, label, value) => {
    if (!hasNativeImage) add(value, "image/*", label);
    return "\n";
  });

  // ComfyUI/OpenClaw tool results commonly arrive as JSON text with a
  // `view_url` field instead of a native image content block. Promote those
  // URLs to real media so the desktop client displays the generated image.
  const toolImageUrlPattern = /["']?(?:view_url|image_url|media_url|mediaUrl)["']?\s*:\s*["'](https?:\/\/[^"'\\\s]+|[A-Za-z]:\\[^"'\\\s]+)["']/gi;
  text = text.replace(toolImageUrlPattern, (_match, value) => {
    add(String(value).replaceAll("\\/", "/"), "image/png", t("generateImage"));
    return "";
  });

  if (Array.isArray(message?.content)) {
    for (const block of message.content) {
      if (block?.type === "image") add(block.url ?? block.source?.url, "image/*", block.alt ?? "");
      if (block?.type === "attachment") {
        const attachment = block.attachment ?? {};
        add(attachment.url ?? attachment.path, attachment.mimeType ?? "", attachment.label ?? "");
      }
    }
  }
  if (typeof message?.mediaUrl === "string") add(message.mediaUrl);
  for (const value of Array.isArray(message?.mediaUrls) ? message.mediaUrls : []) add(value);

  return { text: text.trim(), media, files };
}

function hasVisibleContent(message) {
  if (isHiddenMessage(message)) return false;
  const parts = extractMessageParts(message);
  return Boolean(parts.text || parts.media.length || parts.files.length);
}

function visibleMessages() {
  const messages = state.history.filter(hasVisibleContent);
  if (state.optimistic) {
    const optimisticText = cleanUserText(contentText(state.optimistic.content));
    const exists = messages.some(
      (message) =>
        message.role === "user" &&
        cleanUserText(contentText(message.content)).trim() === optimisticText.trim() &&
        Number(message.timestamp ?? 0) >= state.optimistic.timestamp - 5000
    );
    if (!exists) messages.push(state.optimistic);
  }
  return messages;
}

function createBrandSvg() {
  return `<img class="vela-logo" src="/vela-icon.png?v=4.1.1" alt="" />`;
}

function renderEmptyState() {
  return `
    <div class="empty-state">
      <div class="empty-mark">${createBrandSvg()}</div>
      <h1>${escapeHtml(t("title"))}</h1>
      <p>${escapeHtml(t("subtitle"))}</p>
      <div class="quick-grid">
        <button class="quick-action" type="button" data-quick="image">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 5h16v14H4zM4 16l5-5 4 4 2-2 5 5M16.5 9h.01"></path>
          </svg>
          <strong>${escapeHtml(t("generateImage"))}</strong>
          <span>${escapeHtml(t("generateImageHint"))}</span>
        </button>
        <button class="quick-action" type="button" data-quick="file">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 3h7l4 4v14H7zM14 3v5h5"></path>
          </svg>
          <strong>${escapeHtml(t("analyzeFile"))}</strong>
          <span>${escapeHtml(t("analyzeFileHint"))}</span>
        </button>
        <button class="quick-action" type="button" data-quick="web">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9"></circle>
            <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"></path>
          </svg>
          <strong>${escapeHtml(t("openWeb"))}</strong>
          <span>${escapeHtml(t("openWebHint"))}</span>
        </button>
      </div>
    </div>`;
}

function renderMedia(parts) {
  const images = parts.media.filter((item) => item.kind === "image");
  const videos = parts.media.filter((item) => item.kind === "video");
  const audios = parts.media.filter((item) => item.kind === "audio");
  let html = "";
  if (images.length) {
    html += `<div class="media-grid">${images
      .map(
        (item) => `
          <button class="media-card" type="button" data-media-src="${escapeHtml(item.src)}">
            <img src="${escapeHtml(item.src)}" alt="${escapeHtml(item.label)}" loading="lazy" />
          </button>`
      )
      .join("")}</div>`;
  }
  for (const item of videos) {
    html += `<div class="media-grid"><video class="media-card" src="${escapeHtml(item.src)}" controls></video></div>`;
  }
  for (const item of audios) {
    html += `<div class="file-grid"><audio src="${escapeHtml(item.src)}" controls></audio></div>`;
  }
  if (parts.files.length) {
    html += `<div class="file-grid">${parts.files
      .map(
        (item) => `
          <a class="file-card" href="${escapeHtml(item.src)}" target="_blank" rel="noreferrer">
            <span class="file-card__icon">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v5h5"></path></svg>
            </span>
            <span class="file-card__copy">
              <strong>${escapeHtml(item.label)}</strong>
              <span>${escapeHtml(item.mimeType || t("noText"))}</span>
            </span>
          </a>`
      )
      .join("")}</div>`;
  }
  return html;
}

function renderMessage(message) {
  const user = message.role === "user";
  const parts = extractMessageParts(message);
  const copy = parts.text ? `<div class="message-copy">${renderMarkdown(parts.text)}</div>` : "";
  const meta = formatTime(message.timestamp);
  return `
    <article class="message-row ${user ? "message-row--user" : "message-row--assistant"}">
      ${user ? "" : `<div class="message-avatar">${createBrandSvg()}</div>`}
      <div class="message-body">
        ${copy}
        ${renderMedia(parts)}
        ${meta ? `<div class="message-meta">${escapeHtml(meta)}</div>` : ""}
      </div>
    </article>`;
}

function renderThinking() {
  if (state.activeImageRun) {
    const value = Math.max(1, Math.min(99, Math.round(state.imageProgress.value || 1)));
    const stage = state.imageProgress.stage || t("progressPreparing");
    return `
      <article class="message-row message-row--assistant">
        <div class="message-avatar">${createBrandSvg()}</div>
        <div class="message-body image-progress-card">
          <div class="image-progress-visual" aria-hidden="true">
            <div class="image-progress-orb">
              <i></i><i></i><b></b>
            </div>
            <div class="image-progress-scan"></div>
          </div>
          <div class="image-progress-card__content">
            <div class="image-progress-card__header">
              <strong>${escapeHtml(stage)}</strong>
              <span>${value}%</span>
            </div>
            <div class="image-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}">
              <span style="width:${value}%"></span>
            </div>
            <div class="image-progress-card__detail">${escapeHtml(state.imageProgress.detail || t("progressEstimate"))}</div>
          </div>
        </div>
      </article>`;
  }
  return `
    <article class="message-row message-row--assistant">
      <div class="message-avatar">${createBrandSvg()}</div>
      <div class="message-body">
        <div class="typing" aria-label="${escapeHtml(t("thinking"))}">
          <span></span><span></span><span></span>
        </div>
        <div class="message-meta">${escapeHtml(t("thinking"))}</div>
      </div>
    </article>`;
}

function messagesRenderKey(messages) {
  return JSON.stringify({
    language: state.language,
    pending: state.pending,
    imageProgress: state.activeImageRun ? state.imageProgress : null,
    sessionKey: currentSessionKey,
    messages: messages.map((message) => {
      const parts = extractMessageParts(message);
      return {
        role: message.role,
        timestamp: message.timestamp,
        text: parts.text,
        media: parts.media.map((item) => [item.kind, item.raw, item.label]),
        files: parts.files.map((item) => [item.raw, item.label, item.mimeType])
      };
    })
  });
}

function renderMessages(forceScroll = false) {
  const messages = visibleMessages();
  const previousMessageCount = els.chatContent.querySelectorAll(".message-row").length;
  const renderKey = messagesRenderKey(messages);
  if (renderKey === state.renderedMessagesKey) {
    if (forceScroll) {
      requestAnimationFrame(() => {
        els.chatScroll.scrollTop = messages.length === 0 ? 0 : els.chatScroll.scrollHeight;
      });
    }
    return;
  }

  const wasNearBottom =
    els.chatScroll.scrollHeight - els.chatScroll.scrollTop - els.chatScroll.clientHeight < 48;
  const previousScrollTop = els.chatScroll.scrollTop;
  state.renderedMessagesKey = renderKey;
  els.chatContent.innerHTML =
    messages.length === 0
      ? renderEmptyState()
      : messages.map(renderMessage).join("") + (state.pending ? renderThinking() : "");

  const renderedRows = Array.from(els.chatContent.querySelectorAll(".message-row"));
  renderedRows.slice(Math.max(0, previousMessageCount)).forEach((row, index) => {
    row.classList.add("message-row--fresh");
    row.style.animationDelay = `${Math.min(index * 45, 180)}ms`;
  });

  els.chatContent.querySelectorAll("a").forEach((link) => {
    link.target = "_blank";
    link.rel = "noreferrer";
  });
  els.chatContent.querySelectorAll("[data-media-src]").forEach((button) => {
    button.addEventListener("click", () => openMedia(button.dataset.mediaSrc));
  });
  els.chatContent.querySelectorAll("[data-quick]").forEach((button) => {
    button.addEventListener("click", () => handleQuickAction(button.dataset.quick));
  });
  if (messages.length === 0) {
    requestAnimationFrame(() => {
      els.chatScroll.scrollTop = 0;
    });
  } else if (forceScroll || wasNearBottom) {
    requestAnimationFrame(() => {
      els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
    });
  } else {
    requestAnimationFrame(() => {
      els.chatScroll.scrollTop = previousScrollTop;
    });
  }
}

function renderSessions() {
  els.sessionList.innerHTML = state.sessions
    .map(
      (session) => `
        <button class="session-item ${session.key === currentSessionKey ? "is-active" : ""}" type="button" data-session="${escapeHtml(session.key)}">
          <span class="session-item__icon">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14v10H9l-4 3z"></path></svg>
          </span>
          <span class="session-item__copy">
            <span class="session-item__title">${escapeHtml(session.title || t("untitled"))}</span>
            <span class="session-item__time">${escapeHtml(formatTime(session.updatedAt))}</span>
          </span>
        </button>`
    )
    .join("");
  els.sessionList.querySelectorAll("[data-session]").forEach((button) => {
    button.addEventListener("click", () => setSession(button.dataset.session));
  });
}

function renderHeader() {
  els.chatTitle.textContent = currentSession()?.title || "VELA";
}

function renderCommandDeck() {
  if (!els.commandDeck) return;
  const working = state.pending;
  const image = state.activeImageRun;
  const active = working ? (image ? "execute" : "plan") : "intent";
  const completed = working ? (image ? ["intent", "plan"] : ["intent"]) : [];
  els.commandDeck.classList.toggle("is-working", working);
  els.commandDeck.querySelectorAll("[data-deck-node]").forEach((node) => {
    const name = node.dataset.deckNode;
    node.classList.toggle("is-active", name === active);
    node.classList.toggle("is-complete", completed.includes(name));
  });
  const mode = image ? t("metricImage") : working ? t("metricWorking") : t("metricReady");
  els.deckMode.textContent = mode;
  els.deckSession.textContent = String(state.sessions.length);
  els.deckHistory.textContent = String(state.history.length);
  els.deckStatus.textContent = state.connected ? t("connected") : t("disconnected");
  els.workspaceToggle.textContent = els.commandDeck.classList.contains("is-collapsed") ? t("workspaceOpen") : t("workspaceClose");
}

function renderConnection() {
  els.connectionPill.classList.toggle("is-connected", state.connected);
  els.connectionPill.classList.toggle("is-error", !state.connected && Boolean(state.bootstrap));
  els.connectionLabel.textContent = state.connected ? t("connected") : state.bootstrap ? t("disconnected") : t("connecting");
  els.retryButton.hidden = state.connected;
}

function renderAttachments() {
  els.attachmentStrip.hidden = state.attachments.length === 0;
  els.attachmentStrip.innerHTML = state.attachments
    .map(
      (attachment) => `
        <div class="attachment-chip">
          <span class="attachment-chip__preview">
            ${
              attachment.mimeType.startsWith("image/")
                ? `<img src="${escapeHtml(attachment.dataUrl)}" alt="" />`
                : `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v5h5"></path></svg>`
            }
          </span>
          <span class="attachment-chip__copy">
            <strong>${escapeHtml(attachment.fileName)}</strong>
            <span>${escapeHtml(formatBytes(attachment.sizeBytes))}</span>
          </span>
          <button class="attachment-chip__remove" type="button" data-remove-attachment="${escapeHtml(attachment.id)}">×</button>
        </div>`
    )
    .join("");
  els.attachmentStrip.querySelectorAll("[data-remove-attachment]").forEach((button) => {
    button.addEventListener("click", () => {
      state.attachments = state.attachments.filter((item) => item.id !== button.dataset.removeAttachment);
      renderAttachments();
      updateSendButton();
    });
  });
}

function renderImageStudio() {
  els.imageStudio.hidden = !state.imageMode;
  els.composerInput.placeholder = state.imageMode
    ? state.language === "zh"
      ? "描述你想生成的 4K 画面"
      : "Describe the 4K image you want"
    : t("messagePlaceholder");
  els.imageStudio.querySelectorAll("[data-image-aspect]").forEach((button) => {
    const active = button.dataset.imageAspect === state.imageSettings.aspect;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.imageStudio.querySelectorAll("[data-image-engine]").forEach((button) => {
    const active = button.dataset.imageEngine === state.imageSettings.engine;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.imageStudio.querySelectorAll("[data-image-style]").forEach((button) => {
    const active = button.dataset.imageStyle === state.imageSettings.style;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.imageStudio.querySelectorAll("[data-image-quality]").forEach((button) => {
    const active = button.dataset.imageQuality === state.imageSettings.quality;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.imageStudio.querySelectorAll("[data-image-reference]").forEach((button) => {
    const active = button.dataset.imageReference === state.imageSettings.reference;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.imageStudio.querySelectorAll("[data-image-text]").forEach((button) => {
    const active = button.dataset.imageText === state.imageSettings.textMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function renderWorkspaceNav() {
  els.workspaceNav?.querySelectorAll("[data-workspace-view]").forEach((button) => {
    const active = button.dataset.workspaceView === state.workspaceView;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  if (els.app) els.app.dataset.workspaceView = state.workspaceView;
}

function workspaceLabelKey(view) {
  return {
    tasks: "workspaceTasks",
    plans: "workspacePlans",
    runs: "workspaceRuns",
    models: "workspaceModels",
    tools: "workspaceTools"
  }[view] ?? "workspaceTasks";
}

function statusLabel(status) {
  return {
    ready: t("statusReady"),
    running: t("statusRunning"),
    completed: t("statusCompleted"),
    failed: t("statusFailed"),
    pending: t("statusPending"),
    paused: state.language === "zh" ? "已暂停" : "Paused",
    cancelled: state.language === "zh" ? "已取消" : "Cancelled",
    draft: state.language === "zh" ? "草稿" : "Draft"
  }[String(status ?? "").toLowerCase()] ?? String(status ?? "-");
}

function apiData(payload) {
  return payload?.data ?? payload ?? {};
}

function formatWorkspaceTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : formatTime(date.getTime());
}

function renderWorkspacePanel() {
  if (!els.workspacePanel) return;
  const visible = state.workspaceView !== "chat";
  els.workspacePanel.hidden = !visible;
  if (!visible) return;

  const data = state.workspaceData;
  els.workspacePanelTitle.textContent = t(workspaceLabelKey(state.workspaceView));
  els.workspacePanelSync.textContent = data.loading
    ? t("workspaceSyncing")
    : data.error
      ? t("workspaceOffline")
      : t("workspaceSynced");
  els.workspacePanelSync.classList.toggle("is-error", Boolean(data.error));

  const planCount = data.plans.length;
  const components = Array.isArray(data.status?.components) ? data.status.components : [];
  const onlineCount = components.filter((item) => ["online", "ready", "healthy"].includes(String(item.state))).length;
  const metrics = [
    [t("workspaceStatus"), data.status?.state ?? (data.error ? t("statusOffline") : t("statusOnline"))],
    [t("workspaceSteps"), state.workspaceView === "models" ? String(state.models.items.length) : String(planCount)],
    [t("workspaceUpdated"), formatWorkspaceTime(data.plans[0]?.updated_at ?? data.plans[0]?.updatedAt)]
  ];
  els.workspacePanelMetrics.innerHTML = metrics
    .map(([label, value]) => `<div class="workspace-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");

  if (state.workspaceView === "models") {
    els.workspacePanelList.innerHTML = state.models.items.length
      ? state.models.items.map((item) => `
          <button class="workspace-card workspace-card--model" type="button">
            <span class="workspace-card__signal"></span>
            <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.id)}</small></span>
            <em>${escapeHtml(t("statusOnline"))}</em>
          </button>`).join("")
      : `<div class="workspace-empty">${escapeHtml(t("workspaceEmpty"))}</div>`;
    els.workspacePanelDetail.innerHTML = `
      <div class="workspace-detail__hero"><span class="workspace-detail__eyebrow">${escapeHtml(t("workspaceModels"))}</span><h3>${escapeHtml(state.models.primary || "-")}</h3><p>${escapeHtml(state.language === "zh" ? "当前由 OpenClaw 提供模型路由；生图由本机 ComfyUI 负责。" : "OpenClaw routes chat models locally; ComfyUI handles image generation.")}</p></div>
      <div class="workspace-component-list">${components.map((item) => `<div><span>${escapeHtml(item.name ?? "component")}</span><strong class="status-pill status-pill--${escapeHtml(String(item.state ?? "offline"))}">${escapeHtml(String(item.state ?? "offline"))}</strong></div>`).join("") || `<div class="workspace-empty">${escapeHtml(t("workspaceNoDetail"))}</div>`}</div>`;
    return;
  }

  if (state.workspaceView === "tools") {
    els.workspacePanelList.innerHTML = components.length
      ? components.map((item) => `
          <div class="workspace-card workspace-card--tool">
            <span class="workspace-card__icon">⌘</span>
            <span><strong>${escapeHtml(item.name ?? "Local component")}</strong><small>${escapeHtml(item.detail ?? "")}</small></span>
            <em>${escapeHtml(String(item.state ?? "offline"))}</em>
          </div>`).join("")
      : `<div class="workspace-empty">${escapeHtml(t("workspaceNoDetail"))}</div>`;
    els.workspacePanelDetail.innerHTML = `<div class="workspace-detail__hero"><span class="workspace-detail__eyebrow">${escapeHtml(t("workspaceTools"))}</span><h3>${onlineCount} / ${components.length || 0}</h3><p>${escapeHtml(state.language === "zh" ? "工具和本地服务状态来自真实诊断接口。" : "Tool and local service status comes from the real diagnostics API.")}</p></div>`;
    return;
  }

  els.workspacePanelList.innerHTML = planCount
    ? data.plans.map((plan) => {
        const active = plan.id === data.selectedPlanId;
        const steps = Array.isArray(plan.steps) ? plan.steps : [];
        return `<button class="workspace-card workspace-card--plan${active ? " is-active" : ""}" type="button" data-plan-id="${escapeHtml(plan.id)}">
          <span class="workspace-card__signal workspace-card__signal--${escapeHtml(String(plan.status ?? "pending"))}"></span>
          <span><strong>${escapeHtml(plan.goal ?? plan.id)}</strong><small>${steps.length} ${escapeHtml(t("workspaceSteps"))} · ${escapeHtml(formatWorkspaceTime(plan.updated_at ?? plan.updatedAt))}</small></span>
          <em class="status-pill status-pill--${escapeHtml(String(plan.status ?? "pending"))}">${escapeHtml(statusLabel(plan.status))}</em>
        </button>`;
      }).join("")
    : `<div class="workspace-empty">${escapeHtml(data.error || t("workspaceEmpty"))}</div>`;

  const detail = data.detail;
  if (!detail?.plan) {
    els.workspacePanelDetail.innerHTML = `<div class="workspace-detail__empty"><span>◇</span><p>${escapeHtml(t("workspaceSelectPlan"))}</p></div>`;
    return;
  }
  const plan = detail.plan;
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  const reflections = Array.isArray(detail.reflections) ? detail.reflections : [];
  els.workspacePanelDetail.innerHTML = `
    <div class="workspace-detail__hero">
      <span class="workspace-detail__eyebrow">${escapeHtml(plan.id)}</span>
      <h3>${escapeHtml(plan.goal)}</h3>
      <div class="workspace-detail__meta"><span class="status-pill status-pill--${escapeHtml(String(plan.status))}">${escapeHtml(statusLabel(plan.status))}</span><span>${steps.length} ${escapeHtml(t("workspaceSteps"))}</span><span>${escapeHtml(formatWorkspaceTime(plan.updated_at ?? plan.updatedAt))}</span></div>
    </div>
    <div class="workspace-steps">${steps.map((step, index) => `
      <div class="workspace-step">
        <span class="workspace-step__index">${index + 1}</span>
        <div><strong>${escapeHtml(step.title ?? step.id)}</strong><p>${escapeHtml(step.description ?? "")}</p>${step.result ? `<pre class="workspace-step__result">${escapeHtml(String(step.result).slice(0, 700))}</pre>` : ""}${step.error ? `<pre class="workspace-step__error">${escapeHtml(String(step.error).slice(0, 700))}</pre>` : ""}</div>
        <em class="status-pill status-pill--${escapeHtml(String(step.status ?? "pending"))}">${escapeHtml(statusLabel(step.status))}</em>
      </div>`).join("")}</div>
    ${reflections.length ? `<section class="workspace-reflections"><h4>${escapeHtml(t("reflectionTitle"))}</h4>${reflections.map((item) => `<div class="workspace-reflection"><strong>${escapeHtml(item.failure_type ?? "unknown")}</strong><p>${escapeHtml(item.root_cause ?? item.summary ?? "")}</p><span>${escapeHtml(t("reflectionRetryable"))}: ${item.retryable ? "Yes" : "No"} · ${escapeHtml(t("reflectionSuggested"))}: ${escapeHtml(item.suggested_action ?? "-")}</span></div>`).join("")}</section>` : ""}`;
}

async function refreshWorkspace() {
  if (state.workspaceView === "chat" || state.workspaceData.loading) return;
  state.workspaceData.loading = true;
  renderWorkspacePanel();
  try {
    const headers = { "X-OpenClaw-App-Key": appKey };
    const [statusResponse, plansResponse] = await Promise.all([
      fetch("/api/ocu/status", { headers, cache: "no-store" }),
      fetch("/api/ocu/plans", { headers, cache: "no-store" })
    ]);
    if (!statusResponse.ok || !plansResponse.ok) throw new Error("Local Agent API is unavailable.");
    const statusPayload = await statusResponse.json();
    const plansPayload = await plansResponse.json();
    state.workspaceData.status = apiData(statusPayload);
    state.workspaceData.plans = Array.isArray(apiData(plansPayload).plans) ? apiData(plansPayload).plans : [];
    state.workspaceData.error = "";
    const selected = state.workspaceData.plans.find((plan) => plan.id === state.workspaceData.selectedPlanId) ?? state.workspaceData.plans[0];
    if (selected) await selectWorkspacePlan(selected.id, false);
  } catch (error) {
    state.workspaceData.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.workspaceData.loading = false;
    renderWorkspacePanel();
  }
}

async function selectWorkspacePlan(planId, redraw = true) {
  state.workspaceData.selectedPlanId = planId;
  if (redraw) renderWorkspacePanel();
  try {
    const response = await fetch(`/api/ocu/plans/${encodeURIComponent(planId)}`, {
      headers: { "X-OpenClaw-App-Key": appKey },
      cache: "no-store"
    });
    if (!response.ok) throw new Error("Could not load plan detail.");
    state.workspaceData.detail = apiData(await response.json());
  } catch (error) {
    state.workspaceData.detail = null;
    state.workspaceData.error = error instanceof Error ? error.message : String(error);
  }
  renderWorkspacePanel();
}

function syncWorkspaceTimer() {
  if (state.workspaceView === "chat") {
    if (state.workspaceRefreshTimer) window.clearInterval(state.workspaceRefreshTimer);
    state.workspaceRefreshTimer = null;
    return;
  }
  if (!state.workspaceRefreshTimer) {
    state.workspaceRefreshTimer = window.setInterval(() => void refreshWorkspace(), 5000);
  }
}

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  els.languageLabel.textContent = state.language === "zh" ? "EN" : "中";
  renderAll();
}

function renderAll(forceScroll = false) {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.style.colorScheme = state.theme;
  els.themeButton?.setAttribute("aria-label", state.theme === "dark" ? t("themeLight") : t("themeDark"));
  if (els.themeButton) els.themeButton.title = state.theme === "dark" ? t("themeLight") : t("themeDark");
  els.composer.classList.toggle("is-image-mode", state.imageMode);
  els.imageModeButton.classList.toggle("is-active", state.imageMode);
  renderImageStudio();
  renderRunState();
  renderSessions();
  renderHeader();
  renderConnection();
  renderAttachments();
  renderMessages(forceScroll);
  renderModelPicker();
  renderCommandDeck();
  renderWorkspaceNav();
  renderWorkspacePanel();
  syncWorkspaceTimer();
}

function renderModelPicker() {
  if (!els.modelSelect) return;
  const items = Array.isArray(state.models.items) ? state.models.items : [];
  els.modelSelect.innerHTML = items.length
    ? items.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")
    : `<option value="">${escapeHtml(t("modelLoading"))}</option>`;
  els.modelSelect.value = state.models.primary || items[0]?.id || "";
  els.modelSelect.disabled = !state.connected || !items.length || state.pending;
  els.modelSelect.title = state.models.primary || t("modelLoading");
}

async function loadModels() {
  if (!els.modelSelect) return;
  try {
    const response = await fetch("/api/models", {
      headers: { "X-OpenClaw-App-Key": appKey },
      cache: "no-store"
    });
    if (!response.ok) throw new Error(`Model list failed (${response.status})`);
    state.models = await response.json();
    renderModelPicker();
  } catch (error) {
    renderModelPicker();
    toast(String(error));
  }
}

async function switchModel(modelId) {
  if (!modelId || modelId === state.models.primary || state.pending) return;
  const previous = state.models.primary;
  els.modelSelect.disabled = true;
  toast(t("modelSwitching"));
  try {
    const response = await fetch("/api/model", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-OpenClaw-App-Key": appKey
      },
      body: JSON.stringify({ model: modelId })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || t("modelSwitchFailed"));
    state.models.primary = payload.primary || modelId;
    renderModelPicker();
    toast(`${t("modelSwitched")}: ${payload.label || state.models.primary}`);
  } catch (error) {
    state.models.primary = previous;
    renderModelPicker();
    toast(`${t("modelSwitchFailed")}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function renderRunState() {
  els.sendButton.hidden = state.pending;
  els.stopButton.hidden = !state.pending;
  updateSendButton();
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function toast(message) {
  const element = document.createElement("div");
  element.className = "toast";
  element.textContent = message;
  els.toastRegion.append(element);
  setTimeout(() => {
    element.classList.add("is-leaving");
    setTimeout(() => element.remove(), 380);
  }, 2900);
}

function autoResizeComposer() {
  els.composerInput.style.height = "auto";
  els.composerInput.style.height = `${Math.min(els.composerInput.scrollHeight, 180)}px`;
}

function updateSendButton() {
  els.sendButton.disabled =
    !state.connected ||
    state.pending ||
    (!els.composerInput.value.trim() && state.attachments.length === 0);
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

async function addFiles(fileList) {
  const files = [...fileList];
  if (state.attachments.length + files.length > 8 || files.some((file) => file.size > 25 * 1024 * 1024)) {
    toast(t("fileLimit"));
    return;
  }
  for (const file of files) {
    const dataUrl = await fileToDataUrl(file);
    state.attachments.push({
      id: crypto.randomUUID(),
      dataUrl,
      fileName: file.name,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size
    });
  }
  renderAttachments();
  updateSendButton();
  toast(t("fileAdded"));
}

function attachmentPayloads() {
  return state.attachments.map((attachment) => ({
    type: attachment.mimeType.startsWith("image/") ? "image" : "file",
    mimeType: attachment.mimeType,
    fileName: attachment.fileName,
    content: attachment.dataUrl.split(",", 2)[1] ?? ""
  }));
}

function messageTitle(text) {
  const normalized = cleanUserText(text).replace(/\s+/g, " ").trim();
  if (!normalized) return t("noText");
  return normalized.length > 28 ? `${normalized.slice(0, 28)}…` : normalized;
}

function imageStudioMessage(prompt) {
  const safePrompt = prompt.replace(/\bPROMPT_END\b/gi, "PROMPT END");
  return [
    "OPENCLAW_IMAGE_STUDIO_V2",
    "ACTION=GENERATE_IMAGE",
    "IMPORTANT=直接调用 generate_image 工具并在当前对话返回真实图片，不要只描述步骤或提示词",
    "RETURN_MEDIA=工具返回后保留 outputs[].view_url，使用 MEDIA: URL 或 Markdown 图片返回",
    `ASPECT=${state.imageSettings.aspect}`,
    `STYLE=${state.imageSettings.style}`,
    `QUALITY=${state.imageSettings.quality}`,
    `REFERENCE_MODE=${state.imageSettings.reference}`,
    `TEXT_MODE=${state.imageSettings.textMode}`,
    "RESEARCH_MODE=required",
    "MODEL_ROUTING=auto",
    "MAX_GENERATIONS=1",
    "DESIGN_PHASES=SEMANTIC_PARSE,DETAIL_COMPLETION,COMPOSITION,STYLE_LIGHT_COLOR,CONSISTENCY_CHECK",
    "PIPELINE_ORDER=DESIGN_PLAN,MODEL_ROUTER,ONE_GENERATION,IMMEDIATE_PUBLISH",
    "FORBIDDEN=retry,namesake_substitution",
    "PUBLISH_POLICY=ONE_PASS_IMMEDIATE",
    "RESOLUTION=4K",
    "PROMPT_BEGIN",
    safePrompt,
    "PROMPT_END"
  ].join("\n");
}

async function sendMessage() {
  if (!state.client || !state.connected || state.pending) return;
  const rawText = els.composerInput.value.trim();
  if (!rawText && state.attachments.length === 0) return;

  const isImageRequest = state.imageMode;
  const wireText = isImageRequest ? imageStudioMessage(rawText) : rawText;
  const attachments = attachmentPayloads();
  const runId = crypto.randomUUID();
  const sentAt = Date.now();

  state.optimistic = {
    role: "user",
    content: rawText || t("noText"),
    timestamp: sentAt,
    _optimistic: true
  };
  state.pending = true;
  state.activeRunId = runId;
  state.activeImageRun = isImageRequest;
  state.imageQueueSeen = false;
  state.imageStartedAt = isImageRequest ? Date.now() : 0;
  state.imageProgress = {
    value: isImageRequest ? 2 : 0,
    stage: isImageRequest ? t("progressPreparing") : "",
    detail: isImageRequest ? t("progressEstimate") : ""
  };
  if (isImageRequest) startImageStatusPolling();
  const title = currentSession()?.title;
  if (!title || title === translations.zh.untitled || title === translations.en.untitled) {
    updateCurrentSession({ title: messageTitle(rawText), updatedAt: sentAt });
  } else {
    updateCurrentSession({ updatedAt: sentAt });
  }

  els.composerInput.value = "";
  autoResizeComposer();
  state.attachments = [];
  state.imageMode = false;
  renderAll(true);

  try {
    if (isImageRequest) {
      const response = await fetch("/api/generate-image", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-OpenClaw-App-Key": appKey
        },
        body: JSON.stringify({ prompt: rawText, settings: state.imageSettings })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || t("sendFailed"));
      const outputs = Array.isArray(payload.outputs) ? payload.outputs : [];
      if (!outputs.length) throw new Error("ComfyUI returned no image output.");
      state.history = [
        ...state.history,
        {
          role: "assistant",
          content: outputs.map((output) => `MEDIA: ${output.viewUrl}`).join("\n"),
          timestamp: Date.now()
        }
      ];
      state.pending = false;
      state.activeRunId = null;
      state.optimistic = null;
      stopImageStatusPolling();
      renderAll(true);
      return;
    }
    const response = await state.client.request("chat.send", {
      sessionKey: currentSessionKey,
      agentId: "main",
      message: wireText,
      deliver: false,
      idempotencyKey: runId,
      attachments: attachments.length ? attachments : undefined
    });
    if (response?.runId) state.activeRunId = response.runId;
    scheduleRefresh(450);
  } catch (error) {
    state.pending = false;
    state.activeRunId = null;
    stopImageStatusPolling();
    toast(`${t("sendFailed")}: ${String(error)}`);
    renderAll();
  }
}

async function abortRun() {
  if (!state.client || !state.connected || !state.pending) return;
  try {
    await state.client.request("chat.abort", {
      sessionKey: currentSessionKey,
      ...(state.activeRunId ? { runId: state.activeRunId } : {})
    });
  } catch {
    // The run may already have completed.
  }
  state.pending = false;
  state.activeRunId = null;
  stopImageStatusPolling();
  renderAll();
  scheduleRefresh(250);
}

function scheduleRefresh(delay = 300) {
  clearTimeout(state.refreshTimer);
  state.refreshTimer = setTimeout(() => void refreshHistory(), delay);
}

async function refreshHistory(forceScroll = false) {
  if (!state.client || !state.connected) return;
  if (state.refreshInFlight) {
    state.refreshQueued = true;
    state.refreshForceScroll ||= forceScroll;
    return;
  }

  state.refreshInFlight = true;
  const requestedKey = currentSessionKey;
  try {
    const result = await state.client.request("chat.history", {
      sessionKey: requestedKey,
      agentId: "main",
      limit: 200
    });
    if (requestedKey !== currentSessionKey) return;
    const next = Array.isArray(result?.messages)
      ? result.messages.map(normalizeHistoryMessage)
      : [];
    const previousVisibleCount = state.history.filter(hasVisibleContent).length;
    state.history = next;
    const newestVisible = [...next].reverse().find(hasVisibleContent);
    if (
      state.pending &&
      newestVisible?.role === "assistant" &&
      Number(newestVisible.timestamp ?? 0) >= Number(state.optimistic?.timestamp ?? 0)
    ) {
      state.pending = false;
      state.activeRunId = null;
      stopImageStatusPolling();
    }
    if (
      state.optimistic &&
      next.some(
        (message) =>
          message.role === "user" &&
          Number(message.timestamp ?? 0) >= state.optimistic.timestamp - 5000
      )
    ) {
      state.optimistic = null;
    }
    const nextVisibleCount = next.filter(hasVisibleContent).length;
    renderMessages(forceScroll || nextVisibleCount > previousVisibleCount);
    renderRunState();
  } catch (error) {
    if (!String(error).includes("not found")) {
      console.warn("History refresh failed", error);
    }
  } finally {
    state.refreshInFlight = false;
    if (state.refreshQueued) {
      const queuedForceScroll = state.refreshForceScroll;
      state.refreshQueued = false;
      state.refreshForceScroll = false;
      void refreshHistory(queuedForceScroll);
    }
  }
}

function stopImageStatusPolling() {
  clearInterval(state.imageStatusTimer);
  state.imageStatusTimer = null;
  state.activeImageRun = false;
  state.imageQueueSeen = false;
  state.imageStartedAt = 0;
  state.imageProgress = { value: 0, stage: "", detail: "" };
}

async function refreshImageStatus() {
  if (!state.pending || !state.activeImageRun) return;
  const elapsedSeconds = Math.max(0, (Date.now() - state.imageStartedAt) / 1000);
  try {
    const status = await fetch("/api/image-status", {
      headers: { "X-OpenClaw-App-Key": appKey },
      cache: "no-store"
    }).then((response) => response.json());

    if (!status.online) {
      state.imageProgress = {
        value: 1,
        stage: t("progressOffline"),
        detail: state.language === "zh" ? "正在等待 ComfyUI 启动" : "Waiting for ComfyUI to start"
      };
    } else if (status.running > 0) {
      state.imageQueueSeen = true;
      state.imageProgress = {
        value: Math.min(88, 24 + elapsedSeconds * 0.55),
        stage: t("progressGenerating"),
        detail: state.language === "zh" ? `运行中 · 队列 ${status.pending}` : `Running · ${status.pending} queued`
      };
    } else if (status.pending > 0) {
      state.imageQueueSeen = true;
      state.imageProgress = {
        value: Math.min(22, 14 + elapsedSeconds * 0.12),
        stage: t("progressQueued"),
        detail: state.language === "zh" ? `前方等待 ${status.pending - 1} 个任务` : `${Math.max(0, status.pending - 1)} task(s) ahead`
      };
    } else if (state.imageQueueSeen) {
      state.imageProgress = {
        value: 98,
        stage: t("progressChecking"),
        detail: state.language === "zh" ? "不再进行生成后审查" : "No post-generation review"
      };
    } else {
      const designStages = [
        [t("progressSemantic"), state.language === "zh" ? "识别人物、动物、建筑、物品、场景与动作" : "Identifying subjects, scene and action"],
        [t("progressDetail"), state.language === "zh" ? "补全材质、环境、景深与自然阴影" : "Adding materials, environment, depth and natural shadows"],
        [t("progressComposition"), state.language === "zh" ? "确定视觉重心、机位、焦距与前中后景" : "Setting focus, camera, lens and scene depth"],
        [t("progressStyle"), state.language === "zh" ? "把风格名称转换为可执行的视觉特征" : "Converting style names into visual traits"],
        [t("progressConsistency"), state.language === "zh" ? "消除时间、天气、材质和画风冲突" : "Resolving time, weather, material and style conflicts"],
        [t("progressRouting"), state.language === "zh" ? "匹配动漫、写实或文字专用模型" : "Matching anime, photo or text specialist model"]
      ];
      const designIndex = Math.min(designStages.length - 1, Math.floor(elapsedSeconds / 3));
      state.imageProgress = {
        value: Math.min(18, 2 + designIndex * 3 + (elapsedSeconds % 3)),
        stage: designStages[designIndex][0],
        detail: designStages[designIndex][1]
      };
    }
    renderMessages();
  } catch {
    state.imageProgress = {
      value: Math.min(10, 2 + elapsedSeconds * 0.1),
      stage: t("progressPreparing"),
      detail: state.language === "zh" ? "正在连接本地生图状态" : "Connecting to local image status"
    };
    renderMessages();
  }
}

function startImageStatusPolling() {
  clearInterval(state.imageStatusTimer);
  void refreshImageStatus();
  state.imageStatusTimer = setInterval(() => void refreshImageStatus(), 1000);
}

function startPolling() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => {
    if (state.connected) void refreshHistory();
  }, 2400);
}

async function connectGateway() {
  try {
    state.bootstrap = await fetch("/api/bootstrap", {
      headers: { "X-OpenClaw-App-Key": appKey }
    }).then((response) => {
      if (!response.ok) throw new Error(`Bootstrap failed (${response.status})`);
      return response.json();
    });
    renderConnection();

    const gatewayModule = await import(state.bootstrap.gatewayModuleUrl);
    const GatewayClient =
      gatewayModule.GatewayBrowserClient ??
      gatewayModule.GatewayClient ??
      gatewayModule.t ??
      Object.values(gatewayModule).find(
        (candidate) =>
          typeof candidate === "function" &&
          typeof candidate.prototype?.start === "function" &&
          typeof candidate.prototype?.request === "function"
      );
    if (typeof GatewayClient !== "function") {
      throw new Error("Gateway client compatibility check failed. Update VELA Desktop.");
    }
    state.client?.stop?.();
    state.client = new GatewayClient({
      url: state.bootstrap.gatewayUrl,
      token: state.bootstrap.token,
      clientName: "openclaw-control-ui",
      clientVersion: `openclaw-desktop-${state.bootstrap.version}`,
      platform: "win32",
      mode: "webchat",
      onHello: () => {
        state.connected = true;
        renderConnection();
        renderModelPicker();
        startPolling();
        void refreshHistory(true);
      },
      onClose: () => {
        state.connected = false;
        renderConnection();
      },
      onEvent: (event) => {
        if (
          event?.event === "chat" ||
          event?.event === "session.message" ||
          event?.event === "sessions.changed" ||
          String(event?.event ?? "").startsWith("task")
        ) {
          scheduleRefresh(180);
        }
      }
    });
    state.client.start();
  } catch (error) {
    state.connected = false;
    state.bootstrap = state.bootstrap ?? {};
    renderConnection();
    toast(String(error));
  }
}

function handleQuickAction(kind) {
  if (kind === "file") {
    els.fileInput.click();
    return;
  }
  if (kind === "image") {
    state.imageMode = true;
    renderAll();
    els.composerInput.focus();
    return;
  }
  els.composerInput.value =
    state.language === "zh"
      ? "请联网搜索并整理："
      : "Search the web and synthesize:";
  autoResizeComposer();
  updateSendButton();
  els.composerInput.focus();
}

function openMedia(src) {
  els.mediaDialogImage.src = src;
  els.mediaDialog.showModal();
}

els.newChatButton.addEventListener("click", newSession);
els.languageButton.addEventListener("click", () => {
  state.language = state.language === "zh" ? "en" : "zh";
  localStorage.setItem("openclaw.desktop.language", state.language);
  applyLanguage();
});
els.themeButton.addEventListener("click", () => {
  state.theme = state.theme === "dark" ? "light" : "dark";
  localStorage.setItem("vela.desktop.theme", state.theme);
  document.documentElement.classList.add("theme-transitioning");
  window.setTimeout(() => document.documentElement.classList.remove("theme-transitioning"), 420);
  renderAll();
});
els.workspaceNav?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-workspace-view]");
  if (!button) return;
  state.workspaceView = button.dataset.workspaceView;
  renderAll();
  if (state.workspaceView === "chat") {
    els.composerInput.focus();
    return;
  }
  const label = button.querySelector("[data-i18n]")?.textContent ?? button.dataset.workspaceView;
  toast(`${label} · ${state.language === "zh" ? "正在同步本地 Agent" : "Syncing local agent"}`);
  void refreshWorkspace();
});
els.workspacePanelRefresh?.addEventListener("click", () => void refreshWorkspace());
els.workspacePanelList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-plan-id]");
  if (button) void selectWorkspacePlan(button.dataset.planId);
});
els.sidebarButton.addEventListener("click", () => els.sidebar.classList.toggle("is-open"));
els.retryButton.addEventListener("click", connectGateway);
els.modelSelect?.addEventListener("change", () => void switchModel(els.modelSelect.value));
els.workspaceToggle?.addEventListener("click", () => {
  els.commandDeck.classList.toggle("is-collapsed");
  renderCommandDeck();
});
els.attachButton.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", async () => {
  await addFiles(els.fileInput.files);
  els.fileInput.value = "";
});
els.imageModeButton.addEventListener("click", () => {
  state.imageMode = !state.imageMode;
  if (state.imageMode) toast(t("imageModeActive"));
  renderAll();
  els.composerInput.focus();
});
els.imageStudio.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.imageAspect) state.imageSettings.aspect = button.dataset.imageAspect;
  if (button.dataset.imageEngine) state.imageSettings.engine = button.dataset.imageEngine;
  if (button.dataset.imageStyle) state.imageSettings.style = button.dataset.imageStyle;
  if (button.dataset.imageQuality) state.imageSettings.quality = button.dataset.imageQuality;
  if (button.dataset.imageReference) state.imageSettings.reference = button.dataset.imageReference;
  if (button.dataset.imageText) state.imageSettings.textMode = button.dataset.imageText;
  saveImageSettings();
  renderImageStudio();
  els.composerInput.focus();
});
els.sendButton.addEventListener("click", sendMessage);
els.stopButton.addEventListener("click", abortRun);
els.composerInput.addEventListener("input", () => {
  autoResizeComposer();
  updateSendButton();
});
els.composerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void sendMessage();
  }
});
els.mediaClose.addEventListener("click", () => els.mediaDialog.close());
els.mediaDialog.addEventListener("click", (event) => {
  if (event.target === els.mediaDialog) els.mediaDialog.close();
});

let dragDepth = 0;
window.addEventListener("dragenter", (event) => {
  event.preventDefault();
  dragDepth += 1;
  els.dropOverlay.classList.add("is-visible");
});
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("dragleave", (event) => {
  event.preventDefault();
  dragDepth -= 1;
  if (dragDepth <= 0) {
    dragDepth = 0;
    els.dropOverlay.classList.remove("is-visible");
  }
});
window.addEventListener("drop", async (event) => {
  event.preventDefault();
  dragDepth = 0;
  els.dropOverlay.classList.remove("is-visible");
  await addFiles(event.dataTransfer?.files ?? []);
});

applyLanguage();
renderAll(true);
autoResizeComposer();
void connectGateway();
void loadModels();
