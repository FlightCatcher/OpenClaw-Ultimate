import assert from "node:assert/strict";
import test from "node:test";

import { normalizeMediaPath, resolveMediaUrl } from "../renderer/media.js";

test("normalizes quoted and punctuated media paths", () => {
  assert.equal(normalizeMediaPath('  "C:\\images\\result.png"'), "C:\\images\\result.png");
});

test("restores legacy relative ComfyUI view URLs", () => {
  assert.equal(
    resolveMediaUrl("view?filename=VELA.png&subfolder=&type=output"),
    "http://127.0.0.1:8188/view?filename=VELA.png&subfolder=&type=output"
  );
  assert.equal(
    resolveMediaUrl("/view?filename=VELA.png", { comfyBaseUrl: "http://localhost:8188/" }),
    "http://localhost:8188/view?filename=VELA.png"
  );
});

test("routes local files through the authenticated desktop media endpoint", () => {
  assert.equal(
    resolveMediaUrl("E:\\AI-Models\\Outputs\\image.png", { appKey: "secret key" }),
    "/media?appKey=secret%20key&path=E%3A%5CAI-Models%5COutputs%5Cimage.png"
  );
});

test("preserves absolute web and data URLs", () => {
  assert.equal(resolveMediaUrl("https://example.test/image.png"), "https://example.test/image.png");
  assert.equal(resolveMediaUrl("data:image/png;base64,AAAA"), "data:image/png;base64,AAAA");
});
