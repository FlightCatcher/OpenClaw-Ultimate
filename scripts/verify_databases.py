from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".openclaw").resolve()
    results = []
    healthy = True
    for path in sorted(root.glob("*.db")):
        try:
            with sqlite3.connect(path) as connection:
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                tables = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    ).fetchone()[0]
                )
            ok = integrity.casefold() == "ok"
            results.append(
                {
                    "database": path.name,
                    "ok": ok,
                    "integrity": integrity,
                    "tables": tables,
                    "bytes": path.stat().st_size,
                }
            )
            healthy = healthy and ok
        except (OSError, sqlite3.Error) as exc:
            healthy = False
            results.append(
                {
                    "database": path.name,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    print(json.dumps({"ok": healthy, "databases": results}, ensure_ascii=False, indent=2))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
