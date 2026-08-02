# VELA Image QA

## Scope

本记录覆盖 VELA 桌面端、本地 OpenClaw 工作区、Ollama、ComfyUI，以及三类生图请求：

- 二次元 / 动漫
- 中文拟人动物 / 国漫式原创场景（用于覆盖“有兽焉”类需求）
- 写实摄影 / 野生动物

## Local services checked

- OpenClaw gateway: `127.0.0.1:18789`
- VELA local server: `127.0.0.1:18790`
- ComfyUI: `127.0.0.1:8188`
- Ollama: `127.0.0.1:11434`

## Regression outputs

| Case | Backend | Output |
| --- | --- | --- |
| Anime fox | Animagine XL 4.0 | `E:\AI-Models\Image-Generation\Outputs\vela-qa-anime.png` |
| Anthropomorphic animal illustration | Animagine XL 4.0 | `E:\AI-Models\Image-Generation\Outputs\vela-qa-you-shou-yan.png` |
| Realistic fox photography | RealVisXL V5 | `E:\AI-Models\Image-Generation\Outputs\vela-qa-realistic.png` |
| VELA desktop end-to-end anime request | Animagine XL 4.0 | `E:\AI-Models\Image-Generation\Outputs\OpenClaw_00008_.png` |

## Fixed bug

旧版桌面端的 `/api/generate-image` 固定使用 RealVisXL，无论用户选择动漫还是写实，导致动漫请求生成真人写实图。

现在 VELA 会：

1. 读取图像工作室的样式设置和原始提示词。
2. 将动漫、二次元、国漫、有兽焉、拟人、兽人等请求路由到 Animagine XL。
3. 将写实、摄影、照片、野生动物等请求路由到 RealVisXL。
4. 为不同路线补充对应的正向质量提示词。
5. 把工作室设置从渲染器传递到本地生图服务。

## Verification

- `node --check src/main.mjs` passed.
- `node --check renderer/app.js` passed.
- `git diff --check` passed.
- VELA desktop generation reached `ComfyUI 正在生成` and returned to `就绪`.
- Generated output was visually inspected.

## Limitation

模型仍可能对中文主体词产生偏差；路由和“是否真实出图”已经修复，但具体角色、构图和细节仍受 Animagine 模型的中文语义理解与随机种子影响。
