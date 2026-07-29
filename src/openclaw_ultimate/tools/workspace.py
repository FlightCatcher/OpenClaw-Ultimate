from __future__ import annotations

from pathlib import Path


class WorkspaceAccessError(PermissionError):
    """请求的路径超出了 Agent 工作区。"""


class WorkspaceTools:
    """只允许访问指定根目录的文件工具集合。"""

    _DENIED_DIRECTORY_NAMES = frozenset(
        {
            ".git",
            ".openclaw",
            ".venv",
            "venv",
            "__pycache__",
        }
    )

    def __init__(
        self,
        root: str | Path,
        *,
        max_read_bytes: int = 1_000_000,
        max_results: int = 200,
    ) -> None:
        if max_read_bytes < 1:
            raise ValueError("max_read_bytes must be at least 1.")

        if max_results < 1:
            raise ValueError("max_results must be at least 1.")

        self.root = Path(root).resolve()
        self.max_read_bytes = max_read_bytes
        self.max_results = max_results

        if not self.root.exists():
            raise ValueError(f"Workspace root does not exist: {self.root}")

        if not self.root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {self.root}")

    def list_files(
        self,
        path: str = ".",
        pattern: str = "*",
    ) -> dict[str, object]:
        """列出工作区目录中的文件和子目录。"""

        target = self.resolve_path(path)
        self._validate_pattern(pattern)

        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        entries: list[dict[str, object]] = []

        for entry in sorted(
            target.glob(pattern),
            key=lambda item: (
                not item.is_dir(),
                item.name.lower(),
            ),
        ):
            if self._is_denied_path(entry):
                continue

            entries.append(
                {
                    "path": self.relative_path(entry),
                    "type": ("directory" if entry.is_dir() else "file"),
                    "size": (entry.stat().st_size if entry.is_file() else None),
                }
            )

            if len(entries) >= self.max_results:
                break

        return {
            "path": self.relative_path(target),
            "entries": entries,
            "truncated": (len(entries) >= self.max_results),
        }

    def read_text_file(
        self,
        path: str,
    ) -> dict[str, object]:
        """读取工作区内的 UTF-8 文本文件。"""

        target = self.resolve_path(path)

        if not target.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        if not target.is_file():
            raise IsADirectoryError(f"Path is not a file: {path}")

        size = target.stat().st_size

        if size > self.max_read_bytes:
            raise ValueError(f"File exceeds the {self.max_read_bytes} byte read limit: {path}")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"File is not valid UTF-8 text: {path}") from exc

        return {
            "path": self.relative_path(target),
            "size": size,
            "content": content,
        }

    def search_text(
        self,
        query: str,
        path: str = ".",
        pattern: str = "*",
        case_sensitive: bool = False,
    ) -> dict[str, object]:
        """递归搜索工作区文本文件。"""

        clean_query = query.strip()

        if not clean_query:
            raise ValueError("Search query cannot be empty.")

        target = self.resolve_path(path)
        self._validate_pattern(pattern)

        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        files = (target,) if target.is_file() else target.rglob(pattern)
        needle = clean_query if case_sensitive else clean_query.casefold()
        matches: list[dict[str, object]] = []

        for file_path in files:
            if (
                not file_path.is_file()
                or self._is_denied_path(file_path)
                or file_path.stat().st_size > self.max_read_bytes
            ):
                continue

            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue

            for line_number, line in enumerate(
                lines,
                start=1,
            ):
                haystack = line if case_sensitive else line.casefold()

                if needle not in haystack:
                    continue

                matches.append(
                    {
                        "path": self.relative_path(file_path),
                        "line": line_number,
                        "text": line[:500],
                    }
                )

                if len(matches) >= self.max_results:
                    return {
                        "query": clean_query,
                        "matches": matches,
                        "truncated": True,
                    }

        return {
            "query": clean_query,
            "matches": matches,
            "truncated": False,
        }

    def resolve_path(
        self,
        path: str | Path,
    ) -> Path:
        raw_path = Path(path)
        candidate = (
            raw_path.resolve() if raw_path.is_absolute() else (self.root / raw_path).resolve()
        )

        if candidate != self.root and self.root not in candidate.parents:
            raise WorkspaceAccessError(f"Path is outside the workspace: {path}")

        if self._is_denied_path(candidate):
            raise WorkspaceAccessError(f"Path is protected and cannot be accessed: {path}")

        return candidate

    def relative_path(
        self,
        path: str | Path,
    ) -> str:
        target = self.resolve_path(path)
        relative = target.relative_to(self.root)
        rendered = relative.as_posix()

        return rendered or "."

    @staticmethod
    def _validate_pattern(
        pattern: str,
    ) -> None:
        if not pattern.strip():
            raise ValueError("File pattern cannot be empty.")

        pattern_path = Path(pattern)

        if pattern_path.is_absolute() or ".." in pattern_path.parts:
            raise WorkspaceAccessError(f"File pattern escapes the workspace: {pattern}")

    def _is_denied_path(
        self,
        path: Path,
    ) -> bool:
        try:
            relative = path.resolve().relative_to(self.root)
        except ValueError:
            return True

        if any(part in self._DENIED_DIRECTORY_NAMES for part in relative.parts):
            return True

        name = relative.name.lower()

        return name == ".env" or (name.startswith(".env.") and name != ".env.example")
