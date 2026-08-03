"""Generate a 4K reference-preserving image with FLUX.2 Klein in ComfyUI."""

from __future__ import annotations

import argparse
import json
import secrets
import struct
import time
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from generate_4k import (
    ASPECTS,
    COMFY_URL,
    DRAFT_DIR,
    GENERATION_LOG,
    VERIFIED_GATE_TOKEN,
    prepare_references,
    request_json,
)

DIFFUSION_MODEL = "flux-2-klein-4b-fp8.safetensors"
TEXT_ENCODER = "qwen_3_4b.safetensors"
VAE_MODEL = "flux2-vae.safetensors"
QUALITY_STEPS = {"standard": 4, "high": 6, "ultra": 8}
STYLE_PROMPTS = {
    "auto": "coherent professional image, intentional composition, restrained color grading",
    "natural": "natural imperfections, restrained contrast, nuanced texture, plausible light, subtle color variation, not overprocessed",
    "cinematic": "cinematic motivated light, tactile materials, optical depth, restrained filmic color, subtle grain",
    "photo": "editorial photography, realistic skin and materials, physically plausible light, subtle film grain, no beauty-filter look",
    "anime": "faithful official 2D animation design, controlled line weight, clean silhouette, nuanced cel shading, no glossy 3D rendering",
    "illustration": "refined illustration, tactile brush texture, intentional simplification, cohesive palette, visible artistic decisions",
    "product": "premium product photography, precise geometry, plausible reflections, clean elegant studio composition",
}


def assert_models_available() -> None:
    object_info = request_json("/object_info", timeout=30)
    required = {
        "UNETLoader": DIFFUSION_MODEL,
        "CLIPLoader": TEXT_ENCODER,
        "VAELoader": VAE_MODEL,
    }
    for node, filename in required.items():
        details = object_info.get(node, {})
        options = (
            details.get("input", {})
            .get("required", {})
            .get(
                {
                    "UNETLoader": "unet_name",
                    "CLIPLoader": "clip_name",
                    "VAELoader": "vae_name",
                }[node],
                [[]],
            )[0]
        )
        if filename not in options:
            raise RuntimeError(
                f"FLUX.2 model is not visible to ComfyUI: {filename}. "
                "Finish the model download and restart ComfyUI."
            )


def build_workflow(
    prompt: str,
    aspect: str,
    style: str,
    quality: str,
    seed: int,
    reference_names: list[str],
    negative: str,
) -> tuple[dict, tuple[int, int]]:
    (width, height), target_size = ASPECTS[aspect]
    if reference_names and style in {"auto", "anime", "illustration"}:
        treatment = (
            "reference-locked edit; preserve the exact source character silhouette, "
            "facial geometry, proportions, palette, line weight, flat rendering, and "
            "signature markings; change only what the request explicitly asks; no "
            "redesign, beautification, chibi conversion, mascot reinterpretation, "
            "glossy 3D finish, or extra decorative detail"
        )
    else:
        treatment = STYLE_PROMPTS[style]
    positive = f"{prompt.strip()}. Visual treatment: {treatment}."
    if negative.strip():
        positive += f" Avoid: {negative.strip()}."

    workflow: dict[str, dict] = {
        "1": {
            "inputs": {
                "unet_name": DIFFUSION_MODEL,
                "weight_dtype": "default",
            },
            "class_type": "UNETLoader",
        },
        "2": {
            "inputs": {
                "clip_name": TEXT_ENCODER,
                "type": "flux2",
                "device": "default",
            },
            "class_type": "CLIPLoader",
        },
        "3": {
            "inputs": {"vae_name": VAE_MODEL},
            "class_type": "VAELoader",
        },
        "4": {
            "inputs": {"text": positive, "clip": ["2", 0]},
            "class_type": "CLIPTextEncode",
        },
        "10": {
            "inputs": {"noise_seed": seed},
            "class_type": "RandomNoise",
        },
        "11": {
            "inputs": {"sampler_name": "euler"},
            "class_type": "KSamplerSelect",
        },
        "12": {
            "inputs": {
                "steps": QUALITY_STEPS[quality],
                "width": width,
                "height": height,
            },
            "class_type": "Flux2Scheduler",
        },
        "13": {
            "inputs": {"width": width, "height": height, "batch_size": 1},
            "class_type": "EmptyFlux2LatentImage",
        },
    }

    conditioning: list[object] = ["4", 0]
    for index, reference_name in enumerate(reference_names[:4]):
        load_id = str(30 + index * 4)
        scale_id = str(31 + index * 4)
        encode_id = str(32 + index * 4)
        reference_id = str(33 + index * 4)
        workflow[load_id] = {
            "inputs": {"image": reference_name},
            "class_type": "LoadImage",
        }
        workflow[scale_id] = {
            "inputs": {"image": [load_id, 0]},
            "class_type": "FluxKontextImageScale",
        }
        workflow[encode_id] = {
            "inputs": {"pixels": [scale_id, 0], "vae": ["3", 0]},
            "class_type": "VAEEncode",
        }
        workflow[reference_id] = {
            "inputs": {
                "conditioning": conditioning,
                "latent": [encode_id, 0],
            },
            "class_type": "ReferenceLatent",
        }
        conditioning = [reference_id, 0]

    workflow.update(
        {
            "14": {
                "inputs": {"model": ["1", 0], "conditioning": conditioning},
                "class_type": "BasicGuider",
            },
            "15": {
                "inputs": {
                    "noise": ["10", 0],
                    "guider": ["14", 0],
                    "sampler": ["11", 0],
                    "sigmas": ["12", 0],
                    "latent_image": ["13", 0],
                },
                "class_type": "SamplerCustomAdvanced",
            },
            "16": {
                "inputs": {"samples": ["15", 0], "vae": ["3", 0]},
                "class_type": "VAEDecode",
            },
            "17": {
                "inputs": {
                    "model_name": (
                        "RealESRGAN_x4plus_anime_6B.pth"
                        if style in {"anime", "illustration"}
                        else "RealESRGAN_x4plus.pth"
                    )
                },
                "class_type": "UpscaleModelLoader",
            },
            "18": {
                "inputs": {"upscale_model": ["17", 0], "image": ["16", 0]},
                "class_type": "ImageUpscaleWithModel",
            },
            "19": {
                "inputs": {
                    "image": ["18", 0],
                    "upscale_method": "lanczos",
                    "width": target_size[0],
                    "height": target_size[1],
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },
            "20": {
                "inputs": {
                    "filename_prefix": f"OpenClaw4K/flux2_{aspect}_{style}",
                    "images": ["19", 0],
                },
                "class_type": "SaveImage",
            },
        }
    )
    return workflow, target_size


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
            images = entry.get("outputs", {}).get("20", {}).get("images", [])
            if images:
                return images[0]
        time.sleep(1)
    raise TimeoutError(f"FLUX.2 generation exceeded {timeout_seconds} seconds")


def download_result(image_info: dict, target_size: tuple[int, int], destination_dir: Path) -> Path:
    query = urllib.parse.urlencode(
        {
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
    )
    with urllib.request.urlopen(f"{COMFY_URL}/view?{query}", timeout=120) as response:
        data = response.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ComfyUI returned an invalid PNG image")
    actual_size = struct.unpack(">II", data[16:24])
    if actual_size != target_size:
        raise RuntimeError(f"Unexpected output size: {actual_size}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"OpenClawFlux2_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    destination.write_bytes(data)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--aspect", choices=ASPECTS, default="square")
    parser.add_argument("--style", choices=STYLE_PROMPTS, default="auto")
    parser.add_argument("--quality", choices=QUALITY_STEPS, default="high")
    parser.add_argument("--character", default="")
    parser.add_argument("--negative", default="")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--verification-token", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verification_token != VERIFIED_GATE_TOKEN:
        parser.error(
            "Referenced images are drafts and must be generated through "
            "generate_verified.py; direct publishing is disabled."
        )

    assert_models_available()
    seed = args.seed if args.seed is not None else secrets.randbelow(2**63)
    reference_names, temporary_references = prepare_references(args.reference)
    try:
        workflow, target_size = build_workflow(
            args.prompt,
            args.aspect,
            args.style,
            args.quality,
            seed,
            reference_names,
            args.negative,
        )
        response = request_json(
            "/prompt",
            payload={"prompt": workflow, "client_id": str(uuid.uuid4())},
            timeout=60,
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI rejected the FLUX.2 workflow: {response}")
        image_info = wait_for_output(prompt_id, args.timeout)
        output = download_result(image_info, target_size, DRAFT_DIR)

        GENERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "engine": "flux2-klein-4b-fp8",
            "prompt": args.prompt,
            "aspect": args.aspect,
            "style": args.style,
            "quality": args.quality,
            "seed": seed,
            "character": args.character,
            "references": [str(Path(item).expanduser().resolve()) for item in args.reference],
            "stage": "draft",
            "output": str(output),
            "width": target_size[0],
            "height": target_size[1],
        }
        with GENERATION_LOG.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"Generated FLUX.2 4K image: {target_size[0]}x{target_size[1]}")
        print(f"Seed: {seed}")
        print(f"References: {len(args.reference)}")
        print(f"DRAFT:{output}")
    finally:
        for temporary_reference in temporary_references:
            temporary_reference.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
