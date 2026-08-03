const DEFAULT_COMFY_URL = "http://127.0.0.1:8188";

export function normalizeMediaPath(value) {
  return String(value ?? "")
    .trim()
    .replace(/^["']|["']$/g, "")
    .replace(/[)\]}>,.;]+$/g, "");
}

export function resolveMediaUrl(
  value,
  { appKey = "", comfyBaseUrl = DEFAULT_COMFY_URL } = {}
) {
  const normalized = normalizeMediaPath(value);
  if (!normalized) return "";
  if (/^(?:data:|blob:|https?:)/i.test(normalized)) return normalized;

  // Older OpenClaw/ComfyUI messages persisted a relative `view?...` URL.
  // Resolve those records against ComfyUI so historical images recover when
  // the desktop application is upgraded.
  if (/^\/?view\?/i.test(normalized)) {
    const query = normalized.replace(/^\/?view\?/i, "");
    return `${comfyBaseUrl.replace(/\/$/, "")}/view?${query}`;
  }

  if (/^[A-Za-z]:[\\/]/.test(normalized) || normalized.startsWith("/")) {
    return `/media?appKey=${encodeURIComponent(appKey)}&path=${encodeURIComponent(normalized)}`;
  }
  return normalized;
}
