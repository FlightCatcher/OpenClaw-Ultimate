import assert from "node:assert/strict";
import test from "node:test";

import { looksLikeImageGenerationRequest } from "../renderer/intents.js";

test("recognizes explicit Chinese and English image generation requests", () => {
  assert.equal(looksLikeImageGenerationRequest("帮我生成一张白色机械狐狸的图片"), true);
  assert.equal(looksLikeImageGenerationRequest("画一幅黑白城市插画"), true);
  assert.equal(looksLikeImageGenerationRequest("Generate an image of a lunar base"), true);
});

test("does not route ordinary image questions or negated requests to generation", () => {
  assert.equal(looksLikeImageGenerationRequest("如何生成图片？请解释原理"), false);
  assert.equal(looksLikeImageGenerationRequest("不要生成图片，只分析这段提示词"), false);
  assert.equal(looksLikeImageGenerationRequest("这张图片是什么风格？"), false);
});
