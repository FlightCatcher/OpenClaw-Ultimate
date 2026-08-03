"""Persistent character reference library for OpenClaw Image Studio."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import unicodedata
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

LIBRARY_DIR = Path.home() / ".openclaw" / "workspace" / "memory" / "image-studio" / "characters"
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024
IMAGE_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_name(value: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


def slugify(value: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if slug:
        return slug[:48]
    return f"character-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:10]}"


def load_cards() -> list[tuple[Path, dict]]:
    cards: list[tuple[Path, dict]] = []
    if not LIBRARY_DIR.exists():
        return cards
    for path in LIBRARY_DIR.glob("*/character.json"):
        try:
            cards.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return cards


def find_card(name: str) -> tuple[Path, dict] | None:
    needle = normalize_name(name)
    for path, card in load_cards():
        candidates = [card.get("name", ""), *card.get("aliases", [])]
        if any(normalize_name(candidate) == needle for candidate in candidates):
            return path, card
    return None


class ImageMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value}
        property_name = (values.get("property") or values.get("name") or "").lower()
        if property_name in {"og:image", "og:image:secure_url", "twitter:image"}:
            content = values.get("content")
            if content:
                self.candidates.append(content)


def fetch(url: str) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenClawImageStudio/3.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = response.headers.get_content_type().lower()
        final_url = response.geturl()
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Reference image exceeds 30 MB")
    return data, content_type, final_url


def download_image(url: str, destination_dir: Path) -> tuple[Path, str]:
    data, content_type, final_url = fetch(url)
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = ImageMetaParser()
        parser.feed(data.decode("utf-8", errors="ignore"))
        if not parser.candidates:
            raise ValueError("Page does not expose an og:image or twitter:image reference")
        image_url = urllib.parse.urljoin(final_url, parser.candidates[0])
        data, content_type, final_url = fetch(image_url)

    extension = IMAGE_CONTENT_TYPES.get(content_type)
    if not extension:
        guessed = Path(urllib.parse.urlparse(final_url).path).suffix.lower()
        if guessed not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            raise ValueError(f"URL did not return a supported image ({content_type})")
        extension = ".jpg" if guessed == ".jpeg" else guessed

    destination = destination_dir / f"reference_{uuid.uuid4().hex[:10]}{extension}"
    destination.write_bytes(data)
    return destination, final_url


def import_local(source: str, destination_dir: Path) -> Path:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {path}")
    extension = path.suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        guessed = mimetypes.guess_type(path.name)[0]
        raise ValueError(f"Unsupported reference image: {guessed or extension}")
    destination = destination_dir / f"reference_{uuid.uuid4().hex[:10]}{extension}"
    shutil.copy2(path, destination)
    return destination


def save_card(path: Path, card: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(card, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record_auto_review(name: str, result: dict) -> None:
    """Persist compact QA history without overriding user-authored corrections."""
    found = find_card(name)
    if not found:
        return
    card_path, card = found
    review = {
        "passed": bool(result.get("passed")),
        "score": int(result.get("score", 0)),
        "identityScore": int(result.get("identityScore", 0)),
        "criticalFailures": list(result.get("criticalFailures", []))[:12],
        "retryPrompt": str(result.get("retryPrompt", "")).strip(),
        "output": str(result.get("output", "")),
        "timestamp": str(result.get("reviewedAt") or now()),
    }
    history = [*card.get("autoReviews", []), review][-20:]
    card["autoReviews"] = history
    card["updatedAt"] = now()
    save_card(card_path, card)


def command_add(args: argparse.Namespace) -> None:
    existing = find_card(args.name)
    if existing:
        card_path, card = existing
    else:
        directory = LIBRARY_DIR / slugify(args.name)
        card_path = directory / "character.json"
        card = {
            "name": args.name,
            "aliases": [],
            "traits": "",
            "references": [],
            "feedback": [],
            "uses": 0,
            "createdAt": now(),
        }

    aliases = [*card.get("aliases", []), *args.alias]
    card["aliases"] = list(dict.fromkeys(alias for alias in aliases if alias.strip()))
    if args.traits:
        card["traits"] = args.traits.strip()

    card_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path: Path | None = None
    resolved_source = args.source or ""
    if args.reference:
        reference_path = import_local(args.reference, card_path.parent)
    elif args.url:
        reference_path, resolved_source = download_image(args.url, card_path.parent)
    if reference_path:
        card.setdefault("references", []).append(
            {
                "path": str(reference_path.resolve()),
                "source": resolved_source,
                "addedAt": now(),
            }
        )
        card["activeReference"] = str(reference_path.resolve())
    card["updatedAt"] = now()
    save_card(card_path, card)
    print(json.dumps(card, ensure_ascii=False, indent=2))


def command_find(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(2)
    _, card = found
    print(json.dumps(card, ensure_ascii=False, indent=2))


def command_feedback(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(f"Character not found: {args.name}")
    card_path, card = found
    card.setdefault("feedback", []).append(
        {
            "note": args.note.strip(),
            "rating": args.rating,
            "output": args.output,
            "timestamp": now(),
        }
    )
    card["updatedAt"] = now()
    save_card(card_path, card)
    print(json.dumps(card["feedback"][-1], ensure_ascii=False, indent=2))


def command_touch(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(f"Character not found: {args.name}")
    card_path, card = found
    card["uses"] = int(card.get("uses", 0)) + 1
    card["lastUsedAt"] = now()
    save_card(card_path, card)
    print(card["activeReference"])


def command_activate(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(f"Character not found: {args.name}")
    card_path, card = found
    requested = str(Path(args.reference).expanduser().resolve())
    known = {str(Path(item["path"]).resolve()) for item in card.get("references", [])}
    if requested not in known:
        raise SystemExit("Reference is not registered on this character card")
    card["activeReference"] = requested
    card["updatedAt"] = now()
    save_card(card_path, card)
    print(requested)


def command_activate_set(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(f"Character not found: {args.name}")
    card_path, card = found
    requested = [str(Path(item).expanduser().resolve()) for item in args.reference]
    known = {str(Path(item["path"]).resolve()) for item in card.get("references", [])}
    unknown = [item for item in requested if item not in known]
    if unknown:
        raise SystemExit(f"Unregistered references: {unknown}")
    card["activeReferences"] = requested[:4]
    card["activeReference"] = requested[0] if requested else ""
    card["updatedAt"] = now()
    save_card(card_path, card)
    print(json.dumps(card["activeReferences"], ensure_ascii=False, indent=2))


def command_reject_reference(args: argparse.Namespace) -> None:
    found = find_card(args.name)
    if not found:
        raise SystemExit(f"Character not found: {args.name}")
    card_path, card = found
    requested = str(Path(args.reference).expanduser().resolve())
    kept = []
    rejected = None
    for item in card.get("references", []):
        if str(Path(item["path"]).resolve()) == requested:
            rejected = {**item, "rejectedAt": now(), "reason": args.reason}
        else:
            kept.append(item)
    if not rejected:
        raise SystemExit("Reference is not registered on this character card")
    card["references"] = kept
    card.setdefault("rejectedReferences", []).append(rejected)
    if card.get("activeReference") == requested:
        card["activeReference"] = kept[-1]["path"] if kept else ""
    card["activeReferences"] = [
        item for item in card.get("activeReferences", []) if item != requested
    ]
    card["updatedAt"] = now()
    save_card(card_path, card)
    print(json.dumps(rejected, ensure_ascii=False, indent=2))


def command_list(_: argparse.Namespace) -> None:
    result = [
        {
            "name": card.get("name"),
            "aliases": card.get("aliases", []),
            "activeReference": card.get("activeReference", ""),
            "uses": card.get("uses", 0),
            "feedbackCount": len(card.get("feedback", [])),
        }
        for _, card in load_cards()
    ]
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--alias", action="append", default=[])
    add.add_argument("--traits", default="")
    source = add.add_mutually_exclusive_group()
    source.add_argument("--reference")
    source.add_argument("--url")
    add.add_argument("--source", default="")
    add.set_defaults(handler=command_add)

    find = commands.add_parser("find")
    find.add_argument("--name", required=True)
    find.set_defaults(handler=command_find)

    feedback = commands.add_parser("feedback")
    feedback.add_argument("--name", required=True)
    feedback.add_argument("--note", required=True)
    feedback.add_argument("--rating", type=int, choices=range(1, 6))
    feedback.add_argument("--output", default="")
    feedback.set_defaults(handler=command_feedback)

    touch = commands.add_parser("touch")
    touch.add_argument("--name", required=True)
    touch.set_defaults(handler=command_touch)

    activate = commands.add_parser("activate")
    activate.add_argument("--name", required=True)
    activate.add_argument("--reference", required=True)
    activate.set_defaults(handler=command_activate)

    activate_set = commands.add_parser("activate-set")
    activate_set.add_argument("--name", required=True)
    activate_set.add_argument("--reference", action="append", required=True)
    activate_set.set_defaults(handler=command_activate_set)

    reject_reference = commands.add_parser("reject-reference")
    reject_reference.add_argument("--name", required=True)
    reject_reference.add_argument("--reference", required=True)
    reject_reference.add_argument("--reason", required=True)
    reject_reference.set_defaults(handler=command_reject_reference)

    list_command = commands.add_parser("list")
    list_command.set_defaults(handler=command_list)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
