const NEGATED_IMAGE_REQUEST = /(?:不要|无需|别|禁止)\s*(?:生成|画|绘制|制作|创建).{0,8}(?:图|图片|图像|插画|照片)/i;

const IMAGE_REQUEST_PATTERNS = [
  /^(?:请|麻烦|帮我|给我|我要|我想要|可以)?\s*(?:生成|画|绘制|制作|创建|做)\s*(?:一张|一幅|一个|几张|[1-9]\d*张)?[^。！？\n]{0,80}(?:图|图片|图像|插画|海报|壁纸|头像|照片)/i,
  /(?:帮我|给我|请)\s*(?:生成|画|绘制|制作|创建)[^。！？\n]{0,80}(?:图|图片|图像|插画|海报|壁纸|头像|照片)/i,
  /^(?:please\s+)?(?:generate|create|draw|render|make)\b[^.!?\n]{0,100}\b(?:image|picture|illustration|poster|wallpaper|portrait|photo)\b/i
];

export function looksLikeImageGenerationRequest(value) {
  const text = String(value ?? "").trim();
  if (!text || NEGATED_IMAGE_REQUEST.test(text)) return false;
  return IMAGE_REQUEST_PATTERNS.some((pattern) => pattern.test(text));
}
