from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def _snapshot_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True, timeout=10) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)
        integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise RuntimeError(f"Backup integrity check failed: {source.name}")


def create_backup(
    *,
    project_root: Path,
    backup_root: Path,
    include_openclaw_config: bool,
) -> Path:
    state_root = project_root / ".openclaw"
    if not state_root.is_dir():
        raise FileNotFoundError(f"VELA state directory does not exist: {state_root}")

    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archive_base = backup_root / f"vela-state-{timestamp}"

    with tempfile.TemporaryDirectory(prefix="vela-backup-") as temporary:
        staging = Path(temporary) / "VELA"
        database_root = staging / "state"
        databases: list[str] = []

        for source in sorted(state_root.glob("*.db")):
            destination = database_root / source.name
            _snapshot_database(source, destination)
            databases.append(source.name)

        for source in sorted(state_root.glob("*.json")):
            database_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, database_root / source.name)

        included_openclaw = False
        if include_openclaw_config:
            openclaw_config = Path.home() / ".openclaw" / "openclaw.json"
            if openclaw_config.is_file():
                destination = staging / "openclaw" / "openclaw.json"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(openclaw_config, destination)
                included_openclaw = True

        manifest = {
            "product": "VELA",
            "version": "1.0.0",
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "databases": databases,
            "includes_openclaw_config": included_openclaw,
        }
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        archive = Path(shutil.make_archive(str(archive_base), "zip", staging))

    print(
        json.dumps(
            {
                "ok": True,
                "archive": str(archive),
                "databases": databases,
                "includes_openclaw_config": included_openclaw,
            },
            ensure_ascii=False,
        )
    )
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent VELA state backup.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--include-openclaw-config", action="store_true")
    arguments = parser.parse_args()
    create_backup(
        project_root=arguments.project_root.resolve(),
        backup_root=arguments.backup_root.resolve(),
        include_openclaw_config=arguments.include_openclaw_config,
    )


if __name__ == "__main__":
    main()
