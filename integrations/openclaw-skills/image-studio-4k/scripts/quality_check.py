"""Strict reference-vs-generation quality gate using the local vision model."""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
REVIEW_LOG = (
    Path.home() / ".openclaw" / "workspace" / "memory" / "image-studio" / "quality-reviews.jsonl"
)


def comparison_base64(references: list[str], output: str) -> str:
    reference_paths = [Path(reference).expanduser().resolve() for reference in references[:2]]
    candidate_path = Path(output).expanduser().resolve()
    for source in [*reference_paths, candidate_path]:
        if not source.is_file():
            raise FileNotFoundError(source)

    panel_width, panel_height, label_height = 448, 448, 32
    rows = len(reference_paths)
    canvas = Image.new("RGB", (panel_width * 2, rows * (panel_height + label_height)), "white")
    draw = ImageDraw.Draw(canvas)
    for row, reference_path in enumerate(reference_paths):
        row_top = row * (panel_height + label_height)
        for column, (label, source) in enumerate(
            (
                (f"REFERENCE {row + 1}", reference_path),
                ("CANDIDATE", candidate_path),
            )
        ):
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((panel_width, panel_height), Image.Resampling.LANCZOS)
                left = column * panel_width + (panel_width - image.width) // 2
                top = row_top + label_height + (panel_height - image.height) // 2
                canvas.paste(image, (left, top))
            draw.text(
                (column * panel_width + 14, row_top + 10),
                label,
                fill="black",
            )

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=80, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        return json.loads(match.group(0))


def review(
    reference: str | list[str],
    output: str,
    requirements: str,
    model: str,
    *,
    target_score: int = 88,
    target_identity: int = 90,
) -> dict:
    references = [reference] if isinstance(reference, str) else reference[:2]
    if not references:
        raise ValueError("At least one reference image is required")
    prompt = f"""
You are a strict visual identity inspector, not a friendly art critic.
The attached comparison sheet labels one or two authoritative REFERENCES first
and the generated CANDIDATE last. REFERENCE 1 is authoritative for face and core
identity. When REFERENCE 2 is present, use it for body, tail, costume, or other
features not visible in REFERENCE 1. Expressions and camera angle may differ.

Requested requirements:
{requirements}

Compare only visible evidence. Check species/body silhouette, exact arm and leg
count, face geometry, eye alignment, eye color,
hair/fur, horns/ears, signature markings, clothing/accessories, character count,
pose, composition, invented details, text/logos, anatomy, and synthetic AI-art
artifacts such as waxy/plastic surfaces, excessive glow, oversaturation, incoherent
micro-detail, or accidental symbols.

Treat a third arm, extra limb, fused fingers, malformed hands, asymmetrical eyes,
cross-eyed face, melted facial features, plastic skin, waxy skin, or obvious CGI
surface as a critical failure. Prefer real photographic texture: pores, fine hair,
natural asymmetry, believable light falloff, and material response.

A signature identity error is critical even if the image is attractive. Do not say
"mostly correct" when a critical feature is wrong. Inspect both enlarged rows before
claiming a marking is absent, a horn is off-center, or a color is wrong. Do not
penalize a requested background merely because a reference has a plain background.
A recognizable but generically restyled version is not an identity pass: compare
the exact face shape, eye geometry, head-to-body ratio, silhouette, outline color
and thickness, shading method, detail density, and palette. Treat chibi conversion,
mascot reinterpretation, glossy vector polish, 3D rendering, or beautification as
critical when the requirements ask for the original design.
Return only JSON:
{{
  "passed": true or false,
  "score": integer 0-100,
  "identityScore": integer 0-100,
  "naturalnessScore": integer 0-100,
  "criticalFailures": ["..."],
  "minorIssues": ["..."],
  "matchedTraits": ["..."],
  "retryPrompt": "concise English correction tags"
}}
Pass only when score >= {target_score}, identityScore >= {target_identity}, and
criticalFailures is empty. A high aesthetic score cannot compensate for a wrong
silhouette, face, palette, signature marking, horn/ear/tail, costume, or rendering style.
""".strip()
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0.05},
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [comparison_base64(references, output)],
            }
        ],
    }
    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    message = result.get("message", {})
    raw = message.get("content") or message.get("thinking") or result.get("response") or ""
    if not raw.strip():
        raise RuntimeError(f"Vision model returned no review: {result}")
    try:
        parsed = extract_json(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Vision model returned a non-JSON review: {raw[:2000]!r}") from exc
    model_passed = bool(parsed.get("passed"))
    parsed["modelPassed"] = model_passed
    parsed["passed"] = bool(
        model_passed
        and int(parsed.get("score", 0)) >= target_score
        and int(parsed.get("identityScore", 0)) >= target_identity
        and not parsed.get("criticalFailures")
    )
    parsed["targetScore"] = target_score
    parsed["targetIdentity"] = target_identity
    parsed["model"] = model
    parsed["references"] = [str(Path(item).expanduser().resolve()) for item in references]
    parsed["reference"] = parsed["references"][0]
    parsed["output"] = str(Path(output).expanduser().resolve())
    parsed["reviewedAt"] = datetime.now(UTC).isoformat()
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--model", default="qwen3-vl:8b")
    parser.add_argument("--target-score", type=int, default=88)
    parser.add_argument("--target-identity", type=int, default=90)
    args = parser.parse_args()

    result = review(
        args.reference,
        args.output,
        args.requirements,
        args.model,
        target_score=args.target_score,
        target_identity=args.target_identity,
    )
    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("passed") else 3)


if __name__ == "__main__":
    main()
