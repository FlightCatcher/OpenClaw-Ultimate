"""Generate a polished 4K image with local ComfyUI and Real-ESRGAN."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from character_library import load_cards, normalize_name
from model_router import route_request

COMFY_URL = "http://127.0.0.1:8188"
ANIME_CHECKPOINT = "animagine-xl-4.0.safetensors"
ANIME_OPT_CHECKPOINT = "animagine-xl-4.0-opt.safetensors"
PHOTO_CHECKPOINT = "RealVisXL_V5.0_fp16.safetensors"
HYPER_SDXL_LORA = "Hyper-SDXL-12steps-CFG-lora.safetensors"
MEDIA_DIR = Path.home() / ".openclaw" / "media" / "image-studio-4k"
DRAFT_DIR = MEDIA_DIR / "drafts"
VERIFIED_GATE_TOKEN = "image-studio-verified-v2"
COMFY_INPUT_DIR = Path(r"C:\AI-Apps\ComfyUI_windows_portable\ComfyUI\input")
GENERATION_LOG = (
    Path.home() / ".openclaw" / "workspace" / "memory" / "image-studio" / "generations.jsonl"
)

# The 3060 Ti has 8 GB VRAM.  A 1K SDXL latent plus two IP-Adapter
# references forces Windows into shared-memory paging and can make one image
# take many minutes.  Generate at an identity-friendly 768-class resolution,
# then use the existing high-quality resize stage for the requested 4K asset.
ASPECTS = {
    "square": ((768, 768), (4096, 4096)),
    "landscape": ((896, 512), (3840, 2160)),
    "portrait": ((512, 896), (2160, 3840)),
    "classic": ((832, 640), (3840, 2880)),
    "vertical": ((640, 832), (2880, 3840)),
    "photo": ((896, 576), (3840, 2560)),
}

QUALITY_STEPS = {
    "standard": 10,
    "high": 12,
    "ultra": 38,
}

STYLE_PROMPTS = {
    "auto": "photorealistic, natural lighting, realistic skin and material texture, physically plausible detail, coherent composition, restrained color grading, subtle film grain",
    "natural": "observational detail, natural imperfections, restrained contrast, nuanced texture, subtle color variation, unforced composition",
    "cinematic": "cinematic lighting, motivated practical light, filmic color grading, tactile material texture, optical depth of field, dramatic composition, subtle film grain",
    "photo": "photorealistic, natural lighting, realistic skin and material texture, high dynamic range, subtle film grain, editorial photography, physically plausible detail",
    "anime": "masterpiece, high score, great score, official animation still, controlled line weight, clean silhouette, nuanced cel shading, expressive design",
    "illustration": "editorial illustration, refined brushwork, tactile texture, intentional simplification, cohesive palette, visible artistic decisions",
    "product": "premium product photography, studio lighting, precise reflections, physically plausible materials, elegant clean composition, subtle lens character",
}

COMMON_NEGATIVE = (
    "lowres, blurry, pixelated, jpeg artifacts, compression artifacts, banding, "
    "overexposed, underexposed, muddy colors, text, watermark, signature, username, "
    "bad anatomy, malformed face, asymmetrical face, distorted eyes, cross-eyed, "
    "malformed hands, extra fingers, missing fingers, extra arms, third arm, "
    "multiple arms, extra legs, duplicated limbs, fused limbs, "
    "multiple characters, group, crowd, clone, duplicate subject, repeated character, "
    "split panel, collage, character sheet, "
    "plastic texture, waxy surface, airbrushed skin, oversaturated, overprocessed, "
    "excessive bloom, excessive glow, artificial bokeh, generic AI art, incoherent detail"
)

STYLE_NEGATIVES = {
    "natural": "glossy 3d render, sterile perfection, synthetic texture",
    "cinematic": "anime, illustration, cartoon, CGI, plastic skin",
    "photo": "anime, illustration, cartoon, CGI, plastic skin, beauty-filter skin",
    "product": "cluttered background, warped geometry, inaccurate reflections",
}

PHOTO_STYLES = {"natural", "cinematic", "photo", "product"}
PHOTO_HINTS = {
    "photo",
    "photograph",
    "photoreal",
    "realistic",
    "camera",
    "lens",
    "portrait",
    "editorial",
    "documentary",
    "raw photo",
    "product photography",
}


def known_character_mentions(prompt: str) -> list[str]:
    normalized_prompt = normalize_name(prompt)
    matches: list[str] = []
    for _, card in load_cards():
        names = [card.get("name", ""), *card.get("aliases", [])]
        if any(
            len(normalized := normalize_name(str(name))) >= 2 and normalized in normalized_prompt
            for name in names
        ):
            matches.append(str(card.get("name", "")).strip())
    return list(dict.fromkeys(item for item in matches if item))


def request_json(path: str, *, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{COMFY_URL}{path}", data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def unload_ollama_models() -> None:
    """Free shared GPU memory before ComfyUI loads SDXL on an 8 GB card."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as response:
            loaded = json.loads(response.read().decode("utf-8")).get("models", [])
        for item in loaded:
            model = str(item.get("name") or item.get("model") or "").strip()
            if not model:
                continue
            payload = json.dumps(
                {"model": model, "prompt": "", "stream": False, "keep_alive": 0}
            ).encode("utf-8")
            request = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
    except (OSError, ValueError, json.JSONDecodeError):
        pass


def free_comfy_memory() -> None:
    """Drop stale model caches before loading the selected specialist pipeline."""
    try:
        request_json(
            "/free",
            payload={"unload_models": True, "free_memory": True},
            timeout=30,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Warning: could not free ComfyUI memory: {exc}", file=sys.stderr)


def select_checkpoint(style: str, prompt: str) -> tuple[str, bool]:
    wants_photo = style in PHOTO_STYLES
    if wants_photo:
        try:
            info = request_json("/object_info/CheckpointLoaderSimple", timeout=10)
            choices = (
                info.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
            if PHOTO_CHECKPOINT in choices:
                return PHOTO_CHECKPOINT, True
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Warning: could not inspect photo checkpoints: {exc}", file=sys.stderr)
        print(
            f"Photo checkpoint unavailable; falling back to {ANIME_CHECKPOINT}",
            file=sys.stderr,
        )
    try:
        info = request_json("/object_info/CheckpointLoaderSimple", timeout=10)
        choices = (
            info.get("CheckpointLoaderSimple", {})
            .get("input", {})
            .get("required", {})
            .get("ckpt_name", [[]])[0]
        )
        if ANIME_OPT_CHECKPOINT in choices:
            return ANIME_OPT_CHECKPOINT, False
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Warning: could not inspect anime checkpoints: {exc}", file=sys.stderr)
    return ANIME_CHECKPOINT, False


def prepare_references(references: list[str]) -> tuple[list[str], list[Path]]:
    names: list[str] = []
    destinations: list[Path] = []
    COMFY_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for reference in references:
        source = Path(reference).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Reference image does not exist: {source}")
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            raise ValueError(f"Unsupported reference image type: {source.suffix}")

        filename = f"OpenClawReference_{uuid.uuid4().hex}{source.suffix.lower()}"
        destination = COMFY_INPUT_DIR / filename
        shutil.copy2(source, destination)
        names.append(filename)
        destinations.append(destination)
    return names, destinations


def build_workflow(
    prompt: str,
    aspect: str,
    style: str,
    quality: str,
    seed: int,
    *,
    checkpoint_name: str = ANIME_CHECKPOINT,
    photo_pipeline: bool = False,
    reference_names: list[str] | None = None,
    reference_strength: float = 0.82,
    reference_weight_type: str = "ease out",
    identity_mode: str = "auto",
    extra_negative: str = "",
) -> tuple[dict, tuple[int, int]]:
    (base_width, base_height), (target_width, target_height) = ASPECTS[aspect]
    positive = f"{prompt.strip()}, {STYLE_PROMPTS[style]}"
    negative = COMMON_NEGATIVE
    if style in STYLE_NEGATIVES:
        negative = f"{negative}, {STYLE_NEGATIVES[style]}"
    if extra_negative.strip():
        negative = f"{negative}, {extra_negative.strip()}"
    upscaler = (
        "RealESRGAN_x4plus_anime_6B.pth"
        if style in {"anime", "illustration"}
        else "RealESRGAN_x4plus.pth"
    )

    use_hyper_sdxl = quality == "standard"
    steps = QUALITY_STEPS[quality]
    sampler_name = "euler_ancestral"
    scheduler = "sgm_uniform" if use_hyper_sdxl else "normal"
    cfg = 5.0
    if photo_pipeline:
        if quality == "high":
            steps = 24
        sampler_name = "dpmpp_2m_sde" if use_hyper_sdxl else "dpmpp_sde"
        scheduler = "sgm_uniform" if use_hyper_sdxl else "karras"
        cfg = 5.0 if use_hyper_sdxl else 5.5

    sampler_model = ["14", 0] if use_hyper_sdxl else ["4", 0]
    text_clip = ["14", 1] if use_hyper_sdxl else ["4", 1]
    workflow = {
        "3": {
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": sampler_model,
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
            "class_type": "KSampler",
        },
        "4": {
            "inputs": {"ckpt_name": checkpoint_name},
            "class_type": "CheckpointLoaderSimple",
        },
        "5": {
            "inputs": {
                "width": base_width,
                "height": base_height,
                "batch_size": 1,
            },
            "class_type": "EmptyLatentImage",
        },
        "6": {
            "inputs": {"text": positive, "clip": text_clip},
            "class_type": "CLIPTextEncode",
        },
        "7": {
            "inputs": {"text": negative, "clip": text_clip},
            "class_type": "CLIPTextEncode",
        },
        "8": {
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            "class_type": "VAEDecode",
        },
        "10": {
            "inputs": {"model_name": upscaler},
            "class_type": "UpscaleModelLoader",
        },
        "11": {
            "inputs": {"upscale_model": ["10", 0], "image": ["8", 0]},
            "class_type": "ImageUpscaleWithModel",
        },
        "12": {
            "inputs": {
                "image": ["11", 0],
                "upscale_method": "lanczos",
                "width": target_width,
                "height": target_height,
                "crop": "disabled",
            },
            "class_type": "ImageScale",
        },
        "9": {
            "inputs": {
                "filename_prefix": f"OpenClaw4K/{aspect}_{style}",
                "images": ["12", 0],
            },
            "class_type": "SaveImage",
        },
    }
    if use_hyper_sdxl:
        workflow["14"] = {
            "inputs": {
                "model": ["4", 0],
                "clip": ["4", 1],
                "lora_name": HYPER_SDXL_LORA,
                "strength_model": 1.0,
                "strength_clip": 1.0,
            },
            "class_type": "LoraLoader",
        }
    if quality != "ultra":
        workflow["12"]["inputs"]["image"] = ["8", 0]
        workflow.pop("10")
        workflow.pop("11")
    if reference_names:
        resolved_identity_mode = (
            "face" if identity_mode == "auto" and photo_pipeline else identity_mode
        )
        if resolved_identity_mode == "anchor":
            # A canonical identity calibration uses the clearest first reference
            # directly.  IP-Adapter is deliberately skipped here: at 0.08 denoise
            # the latent already carries the identity, while loading both systems
            # causes severe VRAM swapping on an 8 GB GPU.
            workflow["20"] = {
                "inputs": {"image": reference_names[0]},
                "class_type": "LoadImage",
            }
            workflow["60"] = {
                "inputs": {
                    "image": ["20", 0],
                    "upscale_method": "lanczos",
                    "width": base_width,
                    "height": base_height,
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            }
            workflow["61"] = {
                "inputs": {"pixels": ["60", 0], "vae": ["4", 2]},
                "class_type": "VAEEncode",
            }
            workflow["3"]["inputs"]["latent_image"] = ["61", 0]
            workflow["3"]["inputs"]["denoise"] = 0.02
            return workflow, (target_width, target_height)
        preset = (
            "PLUS FACE (portraits)" if resolved_identity_mode == "face" else "PLUS (high strength)"
        )
        workflow["13"] = {
            "inputs": {
                "model": sampler_model,
                "preset": preset,
            },
            "class_type": "IPAdapterUnifiedLoader",
        }
        prepared_images: list[list[object]] = []
        for index, reference_name in enumerate(reference_names[:4]):
            load_id = str(20 + index * 2)
            prep_id = str(21 + index * 2)
            workflow[load_id] = {
                "inputs": {"image": reference_name},
                "class_type": "LoadImage",
            }
            workflow[prep_id] = {
                "inputs": {
                    "image": [load_id, 0],
                    "interpolation": "LANCZOS",
                    "crop_position": "center",
                    "sharpening": 0.1,
                },
                "class_type": "PrepImageForClipVision",
            }
            prepared_images.append([prep_id, 0])

        combined_image = prepared_images[0]
        for index, prepared_image in enumerate(prepared_images[1:]):
            batch_id = str(40 + index)
            workflow[batch_id] = {
                "inputs": {
                    "image1": combined_image,
                    "image2": prepared_image,
                },
                "class_type": "ImageBatch",
            }
            combined_image = [batch_id, 0]

        workflow["16"] = {
            "inputs": {
                "model": ["13", 0],
                "ipadapter": ["13", 1],
                "image": combined_image,
                "weight": reference_strength,
                "weight_type": reference_weight_type,
                "combine_embeds": "average",
                "start_at": 0.0,
                "end_at": 0.9 if reference_strength >= 0.9 else 0.78,
                "embeds_scaling": "K+V" if reference_strength >= 0.9 else "K+V w/ C penalty",
            },
            "class_type": "IPAdapterAdvanced",
        }
        workflow["3"]["inputs"]["model"] = ["16", 0]
        if resolved_identity_mode != "face":
            # For full-body anime/creature identities, use the final reference as
            # a low-denoise structural anchor as well as IP-Adapter guidance.
            # This prevents an obscure character from collapsing into a generic
            # mascot while still allowing modest scene and expression changes.
            structure_index = (
                0 if resolved_identity_mode == "anchor" else min(len(reference_names), 4) - 1
            )
            structure_load_id = str(20 + structure_index * 2)
            workflow["60"] = {
                "inputs": {
                    "image": [structure_load_id, 0],
                    "upscale_method": "lanczos",
                    "width": base_width,
                    "height": base_height,
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            }
            workflow["61"] = {
                "inputs": {"pixels": ["60", 0], "vae": ["4", 2]},
                "class_type": "VAEEncode",
            }
            workflow["3"]["inputs"]["latent_image"] = ["61", 0]
            workflow["3"]["inputs"]["denoise"] = (
                0.08 if resolved_identity_mode == "anchor" else 0.16
            )
    return workflow, (target_width, target_height)


def wait_for_output(prompt_id: str, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        history = request_json(f"/history/{urllib.parse.quote(prompt_id)}", timeout=30)
        entry = history.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                messages = status.get("messages", [])
                raise RuntimeError(f"ComfyUI failed: {messages[-1] if messages else status}")
            images = entry.get("outputs", {}).get("9", {}).get("images", [])
            if images:
                return images[0]
        time.sleep(1.0)
    raise TimeoutError(f"ComfyUI did not finish within {timeout_seconds} seconds")


def download_result(image_info: dict, target_size: tuple[int, int]) -> Path:
    query = urllib.parse.urlencode(
        {
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
    )
    with urllib.request.urlopen(f"{COMFY_URL}/view?{query}", timeout=120) as response:
        image_bytes = response.read()
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ComfyUI returned an invalid PNG image")
    actual_size = struct.unpack(">II", image_bytes[16:24])
    if actual_size != target_size:
        raise RuntimeError(f"Unexpected output size: {actual_size[0]}x{actual_size[1]}")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    destination = MEDIA_DIR / f"OpenClaw4K_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    destination.write_bytes(image_bytes)
    return destination


def log_generation(
    *,
    prompt: str,
    aspect: str,
    style: str,
    quality: str,
    seed: int,
    character: str,
    references: list[str],
    reference_strength: float,
    reference_weight_type: str,
    checkpoint: str,
    output_path: Path,
    target_size: tuple[int, int],
) -> None:
    GENERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "prompt": prompt,
        "aspect": aspect,
        "style": style,
        "quality": quality,
        "seed": seed,
        "character": character,
        "references": references,
        "referenceStrength": reference_strength if references else 0,
        "referenceWeightType": reference_weight_type if references else "",
        "checkpoint": checkpoint,
        "output": str(output_path),
        "width": target_size[0],
        "height": target_size[1],
    }
    with GENERATION_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--aspect", choices=ASPECTS, default="square")
    parser.add_argument("--style", choices=STYLE_PROMPTS, default="auto")
    parser.add_argument("--quality", choices=QUALITY_STEPS, default="high")
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Local reference image for IP-Adapter identity conditioning; repeat up to four times",
    )
    parser.add_argument("--reference-strength", type=float, default=0.82)
    parser.add_argument(
        "--identity-mode",
        choices=("auto", "face", "general", "anchor"),
        default="auto",
        help="Use face identity conditioning for human portraits or general conditioning for full characters",
    )
    parser.add_argument(
        "--reference-weight-type",
        choices=("ease out", "linear", "style transfer"),
        default="ease out",
        help="How strongly the reference may influence composition; ease out preserves prompt control",
    )
    parser.add_argument("--character", default="")
    parser.add_argument("--negative", default="")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--verification-token", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0.0 <= args.reference_strength <= 1.5:
        parser.error("--reference-strength must be between 0 and 1.5")
    named_matches = known_character_mentions(args.prompt)
    if named_matches and not args.reference:
        parser.error(
            "Known character mention requires verified references: "
            f"{', '.join(named_matches)}. Use generate_verified.py."
        )
    if args.reference and args.verification_token != VERIFIED_GATE_TOKEN:
        parser.error(
            "Referenced images are drafts and must be generated through "
            "generate_verified.py; direct publishing is disabled."
        )

    unload_ollama_models()
    free_comfy_memory()
    seed = args.seed if args.seed is not None else secrets.randbelow(2**63)
    route = route_request(
        args.prompt,
        requested_style=args.style,
        identity_context=args.character,
        has_reference=bool(args.reference),
    )
    resolved_style = route.style
    checkpoint, photo_pipeline = select_checkpoint(resolved_style, args.prompt)
    reference_names, temporary_references = prepare_references(args.reference)
    try:
        workflow, target_size = build_workflow(
            args.prompt,
            args.aspect,
            resolved_style,
            args.quality,
            seed,
            checkpoint_name=checkpoint,
            photo_pipeline=photo_pipeline,
            reference_names=reference_names,
            reference_strength=args.reference_strength,
            reference_weight_type=args.reference_weight_type,
            identity_mode=(
                route.identity_mode if args.identity_mode == "auto" else args.identity_mode
            ),
            extra_negative=args.negative,
        )
        response = request_json(
            "/prompt",
            payload={"prompt": workflow, "client_id": str(uuid.uuid4())},
            timeout=30,
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI rejected the workflow: {response}")
        image_info = wait_for_output(prompt_id, args.timeout)
        output_path = download_result(image_info, target_size)
        if args.reference:
            DRAFT_DIR.mkdir(parents=True, exist_ok=True)
            draft_path = DRAFT_DIR / output_path.name
            output_path.replace(draft_path)
            output_path = draft_path
        log_generation(
            prompt=args.prompt,
            aspect=args.aspect,
            style=resolved_style,
            quality=args.quality,
            seed=seed,
            character=args.character,
            references=[str(Path(item).expanduser().resolve()) for item in args.reference],
            reference_strength=args.reference_strength,
            reference_weight_type=args.reference_weight_type,
            checkpoint=checkpoint,
            output_path=output_path,
            target_size=target_size,
        )

        print(f"Generated 4K image: {target_size[0]}x{target_size[1]}")
        print(f"Seed: {seed}")
        print(f"Checkpoint: {checkpoint}")
        print(f"Model route: {route.family} ({route.reason})")
        if args.reference:
            print(
                f"Reference conditioning: {args.reference_strength:.2f}, "
                f"{args.reference_weight_type} "
                f"({len(args.reference)} image{'s' if len(args.reference) != 1 else ''})"
            )
        print(f"{'DRAFT' if args.reference else 'MEDIA'}:{output_path}")
    finally:
        for temporary_reference in temporary_references:
            temporary_reference.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
