"""Check whether a candidate image is clean enough for character conditioning."""

from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
REVIEW_LOG = (
    Path.home() / ".openclaw" / "workspace" / "memory" / "image-studio" / "reference-reviews.jsonl"
)


def encode_image(path: str) -> tuple[str, str]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    return base64.b64encode(source.read_bytes()).decode("ascii"), str(source)


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        return json.loads(match.group(0))


def inspect(image: str, expected: str, model: str) -> dict:
    encoded, resolved = encode_image(image)
    prompt = f"""
You are curating clean visual-conditioning data for an image generator.
Inspect the attached candidate image. The expected subject is:
{expected}

Judge only visible evidence. A useful reference must clearly show the expected
subject and its stable identity traits. Reject wrong characters, fan redesigns
that change the base costume/body, tiny or heavily occluded subjects, collages,
promotional layouts, subtitles, large titles, logos, signatures, and watermarks.
A normal background is acceptable. Small incidental objects are acceptable only
when they do not cover the subject. Return only JSON:
{{
  "usable": true or false,
  "subjectMatchScore": integer 0-100,
  "identityVisibilityScore": integer 0-100,
  "mainSubjectClear": true or false,
  "hasOverlayText": true or false,
  "hasWatermarkOrLogo": true or false,
  "isPromotionalLayout": true or false,
  "suspectedFanRedesign": true or false,
  "visibleIdentityTraits": ["..."],
  "rejectionReasons": ["..."],
  "cropSuggestion": "none or a concise crop instruction"
}}
Set usable=true only when both scores are at least 80, mainSubjectClear=true,
there is no overlay text/logo/watermark, it is not a promotional layout, and no
identity-changing fan redesign is visible.

The expected-subject specification above is authoritative. Do not use your own
memory of the franchise to contradict a listed color, horn, marking, tail, costume,
or rendering trait. Mark a fan redesign only when the image visibly conflicts with
that specification or with another supplied authoritative trait—not merely because
the design differs from your prior knowledge.
""".strip()
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0.0},
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [encoded],
            }
        ],
    }
    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.loads(response.read().decode("utf-8"))
    message = raw.get("message", {})
    review_text = message.get("content") or message.get("thinking") or raw.get("response") or ""
    if not review_text.strip():
        raise RuntimeError(f"Vision model returned no reference review: {raw}")
    try:
        result = extract_json(review_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Vision model returned a non-JSON reference review: {review_text[:2000]!r}"
        ) from exc

    required = (
        int(result.get("subjectMatchScore", 0)) >= 80
        and int(result.get("identityVisibilityScore", 0)) >= 80
        and bool(result.get("mainSubjectClear"))
        and not bool(result.get("hasOverlayText"))
        and not bool(result.get("hasWatermarkOrLogo"))
        and not bool(result.get("isPromotionalLayout"))
        and not bool(result.get("suspectedFanRedesign"))
    )
    result["usable"] = bool(result.get("usable")) and required
    result["model"] = model
    result["image"] = resolved
    result["expected"] = expected
    result["reviewedAt"] = datetime.now(UTC).isoformat()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--model", default="qwen3-vl:8b")
    args = parser.parse_args()

    result = inspect(args.image, args.expected, args.model)
    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["usable"] else 3)


if __name__ == "__main__":
    main()
