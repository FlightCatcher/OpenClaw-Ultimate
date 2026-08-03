"""Create and validate a bounded pre-generation research record."""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

RESEARCH_DIR = Path.home() / ".openclaw" / "workspace" / "memory" / "image-studio" / "research"


def valid_source(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def create_manifest(
    subject: str,
    query: str,
    sources: list[str],
    references: list[str],
    identity_summary: str,
    temporary_references: list[str] | None = None,
) -> Path:
    cleaned_sources = list(dict.fromkeys(item.strip() for item in sources if item.strip()))
    if not cleaned_sources or not all(valid_source(item) for item in cleaned_sources):
        raise ValueError("At least one valid http(s) research source is required")
    resolved_references = [str(Path(item).expanduser().resolve()) for item in references]
    missing = [item for item in resolved_references if not Path(item).is_file()]
    if missing:
        raise FileNotFoundError(f"Research references are missing: {missing}")
    if len(identity_summary.strip()) < 20:
        raise ValueError("Identity summary is too short to prevent namesake confusion")

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    path = RESEARCH_DIR / f"research_{int(time.time())}_{uuid.uuid4().hex[:8]}.json"
    record = {
        "subject": subject.strip(),
        "query": query.strip(),
        "sources": cleaned_sources[:6],
        "references": resolved_references[:4],
        "temporaryReferences": [
            str(Path(item).expanduser().resolve())
            for item in (temporary_references or [])
            if Path(item).expanduser().resolve().is_file()
        ],
        "identitySummary": identity_summary.strip(),
        "createdAt": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_valid_manifest(path: str, subject: str, references: list[str]) -> dict:
    source = Path(path).expanduser().resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not str(data.get("subject", "")).strip():
        raise ValueError("Research manifest has no subject")
    wanted = re.sub(r"\W+", "", subject.casefold())
    recorded = re.sub(r"\W+", "", str(data["subject"]).casefold())
    if wanted and recorded and wanted not in recorded and recorded not in wanted:
        raise ValueError("Research manifest subject does not match generation subject")
    if not data.get("sources") or not all(valid_source(item) for item in data["sources"]):
        raise ValueError("Research manifest has no valid sources")
    created = datetime.fromisoformat(str(data["createdAt"]))
    age = datetime.now(UTC) - created.astimezone(UTC)
    if age.total_seconds() > 86400:
        raise ValueError("Research manifest is older than 24 hours; research again")
    researched_refs = {
        str(Path(item).expanduser().resolve()).casefold() for item in data.get("references", [])
    }
    requested_refs = {str(Path(item).expanduser().resolve()).casefold() for item in references}
    if requested_refs and not requested_refs.intersection(researched_refs):
        raise ValueError("Generation references were not included in the research manifest")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--identity-summary", required=True)
    parser.add_argument("--temporary-reference", action="append", default=[])
    args = parser.parse_args()
    print(
        create_manifest(
            args.subject,
            args.query,
            args.source,
            args.reference,
            args.identity_summary,
            args.temporary_reference,
        )
    )


if __name__ == "__main__":
    main()
