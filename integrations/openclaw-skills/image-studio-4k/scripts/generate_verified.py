"""Generate and immediately publish one reference-locked image."""

from __future__ import annotations

import argparse
import atexit
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from character_library import find_card, record_auto_review
from generate_4k import MEDIA_DIR, VERIFIED_GATE_TOKEN
from model_router import route_request
from quality_check import review
from research_manifest import load_valid_manifest

SCRIPT_DIR = Path(__file__).resolve().parent
ANIMAGINE_GENERATOR = SCRIPT_DIR / "generate_4k.py"
FLUX2_GENERATOR = SCRIPT_DIR / "generate_flux2.py"
CREATURE_TERMS = {
    "animal",
    "beast",
    "creature",
    "mascot",
    "pixiu",
    "qilin",
    "dragon",
    "fox",
    "wolf",
    "dog",
    "cat",
    "deer",
    "rabbit",
    "fur",
    "horn",
    "tail",
    "异兽",
    "动物",
    "神兽",
    "貔貅",
    "麒麟",
    "龙",
    "狐狸",
    "狼",
    "犬",
    "猫",
    "鹿",
    "兔",
    "毛发",
    "角",
    "尾巴",
}


def normalize_single_subject(prompt: str, requirements: str) -> str:
    """Prevent a named solo creature from being interpreted as a human group."""
    context = f"{prompt} {requirements}".lower()
    wants_solo = bool(
        re.search(r"\bsolo\b|single (?:character|subject)|exactly one|单只|单个|独自", context)
    )
    is_creature = any(term in context for term in CREATURE_TERMS)
    if not (wants_solo and is_creature):
        return prompt
    cleaned = re.sub(r"\b1(?:boy|girl)\b", "1other", prompt, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:boy|girl),\s*solo\b", "1other, solo", cleaned, flags=re.IGNORECASE)
    return (
        "1other, solo, single character, exactly one subject, centered composition, "
        "no companion, no duplicate, " + cleaned
    )


def run_generator(
    args: argparse.Namespace,
    prompt: str,
    strength: float,
    weight_type: str,
    *,
    resolved_engine: str,
    resolved_style: str,
    identity_mode: str,
) -> Path:
    generator = FLUX2_GENERATOR if resolved_engine == "flux2" else ANIMAGINE_GENERATOR
    command = [
        sys.executable,
        str(generator),
        "--prompt",
        prompt,
        "--aspect",
        args.aspect,
        "--style",
        resolved_style,
        "--quality",
        args.quality,
        "--character",
        args.character,
        "--negative",
        args.negative,
        "--timeout",
        str(args.timeout),
        "--verification-token",
        VERIFIED_GATE_TOKEN,
    ]
    if resolved_engine == "animagine":
        command.extend(
            (
                "--reference-strength",
                str(strength),
                "--reference-weight-type",
                weight_type,
                "--identity-mode",
                identity_mode,
            )
        )
    for reference in args.reference:
        command.extend(("--reference", reference))
    if args.seed is not None:
        command.extend(("--seed", str(args.seed)))

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise RuntimeError(f"Image generator exited with code {result.returncode}")

    match = re.search(r"^DRAFT:(.+)$", result.stdout, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Image generator did not return a quarantined draft path")
    output = Path(match.group(1).strip()).resolve()
    if not output.is_file():
        raise RuntimeError(f"Generated image is missing: {output}")
    return output


def load_identity_policy(character: str) -> tuple[str, str]:
    found = find_card(character)
    if not found:
        return "", ""
    _, card = found
    traits = str(card.get("traits", "")).strip()
    style_lock = str(card.get("styleLock", "")).strip()
    feedback = [
        str(item.get("note", "")).strip()
        for item in card.get("feedback", [])
        if str(item.get("note", "")).strip()
    ]
    requirements = "; ".join(item for item in (traits, style_lock, *feedback[-4:]) if item)
    prefix = (
        "REFERENCE-LOCKED CHARACTER EDIT. Reference 1 is authoritative for the "
        "face and core identity; the remaining references fill body and costume "
        "details. Preserve exact silhouette, facial geometry, proportions, palette, "
        "line weight, rendering style, and signature markings. Change only the "
        "requested pose, expression, action, camera, or background. Do not redesign, "
        "beautify, chibify, modernize, add decorative detail, or turn the subject "
        "into a generic mascot."
    )
    if requirements:
        prefix += f" Mandatory identity specification: {requirements}."
    return prefix, requirements


def promote_draft(draft: Path, engine: str) -> Path:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    prefix = "OpenClawFlux2" if engine == "flux2" else "OpenClaw4K"
    final = MEDIA_DIR / f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    shutil.move(str(draft), str(final))
    return final


def free_comfy_memory() -> None:
    """Unload the diffusion checkpoint before starting the local vision reviewer."""
    request = urllib.request.Request(
        "http://127.0.0.1:8188/free",
        data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            pass
    except OSError as exc:  # best-effort memory protection
        print(f"Warning: could not unload ComfyUI before review: {exc}", flush=True)


def corrected_prompt(prompt: str, result: dict) -> str:
    failures = [
        str(item).strip() for item in result.get("criticalFailures", []) if str(item).strip()
    ]
    issues = [str(item).strip() for item in result.get("minorIssues", []) if str(item).strip()]
    retry = str(result.get("retryPrompt", "")).strip()
    correction = "; ".join([*failures[:6], *issues[:4], retry])
    if not correction:
        correction = "match the authoritative references more literally; preserve exact identity"
    return (
        f"{prompt} STRICT RETRY CORRECTION: {correction}. "
        "Do not change already-correct traits, subject count, requested scene, or camera."
    )


def cleanup_temporary_references(research: dict) -> None:
    """Delete only session references explicitly marked temporary by research."""
    for item in research.get("temporaryReferences", []):
        try:
            Path(item).expanduser().resolve().unlink(missing_ok=True)
        except OSError as exc:
            print(f"Warning: could not delete temporary reference {item}: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--character", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument(
        "--aspect",
        choices=("square", "landscape", "portrait", "classic", "vertical", "photo"),
        default="square",
    )
    parser.add_argument(
        "--style",
        choices=("auto", "natural", "cinematic", "photo", "anime", "illustration", "product"),
        default="auto",
    )
    parser.add_argument("--quality", choices=("standard", "high", "ultra"), default="high")
    parser.add_argument("--engine", choices=("auto", "animagine", "flux2"), default="auto")
    parser.add_argument("--text-mode", choices=("auto", "clear", "none"), default="auto")
    parser.add_argument("--reference-strength", type=float, default=0.72)
    parser.add_argument(
        "--reference-weight-type",
        choices=("ease out", "linear", "style transfer"),
        default="ease out",
    )
    parser.add_argument("--negative", default="")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--identity-mode",
        choices=("auto", "face", "general", "anchor"),
        default="auto",
    )
    parser.add_argument("--research-manifest", required=True)
    parser.add_argument("--attempts", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--vision-model", default="qwen3-vl:8b")
    parser.add_argument("--target-score", type=int, default=88)
    parser.add_argument("--target-identity", type=int, default=90)
    args = parser.parse_args()

    identity_prefix, card_requirements = load_identity_policy(args.character)
    requirements = "; ".join(
        item for item in (args.requirements.strip(), card_requirements) if item
    )
    research = load_valid_manifest(
        args.research_manifest,
        args.character,
        args.reference,
    )
    atexit.register(cleanup_temporary_references, research)
    research_identity = str(research.get("identitySummary", "")).strip()
    requirements = "; ".join(item for item in (requirements, research_identity) if item)
    scene_prompt = normalize_single_subject(args.prompt, requirements)
    prompt = f"{identity_prefix} Requested scene: {scene_prompt}".strip()
    route = route_request(
        args.prompt,
        requested_style=args.style,
        identity_context=requirements,
        has_reference=bool(args.reference),
        text_mode=args.text_mode,
    )
    resolved_engine = route.engine if args.engine == "auto" else args.engine
    resolved_style = route.style
    identity_mode = route.identity_mode if args.identity_mode == "auto" else args.identity_mode
    print(
        f"Selected route: {route.family}; engine={resolved_engine}; "
        f"style={resolved_style}; reason={route.reason}",
        flush=True,
    )
    strength = args.reference_strength
    weight_type = args.reference_weight_type
    if resolved_engine == "animagine" and args.reference:
        strength = max(strength, 0.95)
        weight_type = "linear"
    attempts: list[tuple[Path, dict]] = []
    current_prompt = prompt
    for attempt in range(1, args.attempts + 1):
        print(f"Identity-locked attempt {attempt}/{args.attempts}", flush=True)
        output = run_generator(
            args,
            current_prompt,
            strength,
            weight_type,
            resolved_engine=resolved_engine,
            resolved_style=resolved_style,
            identity_mode=identity_mode,
        )
        free_comfy_memory()
        result = review(
            args.reference,
            str(output),
            requirements,
            args.vision_model,
            target_score=args.target_score,
            target_identity=args.target_identity,
            calibration_anchor=args.identity_mode == "anchor",
        )
        record_auto_review(args.character, result)
        attempts.append((output, result))
        print(
            "Identity review: "
            f"score={int(result.get('score', 0))}, "
            f"identity={int(result.get('identityScore', 0))}, "
            f"passed={bool(result.get('passed'))}",
            flush=True,
        )
        if result.get("passed"):
            final = promote_draft(output, resolved_engine)
            for draft, _ in attempts:
                if draft != output:
                    draft.unlink(missing_ok=True)
            print(f"IDENTITY_SCORE:{int(result.get('identityScore', 0))}", flush=True)
            print(f"QUALITY_SCORE:{int(result.get('score', 0))}", flush=True)
            print(f"MEDIA:{final}", flush=True)
            cleanup_temporary_references(research)
            return
        current_prompt = corrected_prompt(prompt, result)
        strength = min(1.0, strength + 0.03)
        weight_type = "linear"

    best_output, best_result = max(
        attempts,
        key=lambda item: (
            int(item[1].get("identityScore", 0)),
            int(item[1].get("score", 0)),
        ),
    )
    for draft, _ in attempts:
        if draft != best_output:
            draft.unlink(missing_ok=True)
    print(f"BEST_DRAFT:{best_output}", flush=True)
    print(f"IDENTITY_SCORE:{int(best_result.get('identityScore', 0))}", flush=True)
    print(f"QUALITY_SCORE:{int(best_result.get('score', 0))}", flush=True)
    print("Identity threshold was not reached; no image was published.", file=sys.stderr)
    cleanup_temporary_references(research)
    raise SystemExit(4)


if __name__ == "__main__":
    main()
