from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from openclaw_ultimate.tools.workspace import (
    WorkspaceAccessError,
    WorkspaceTools,
)


class SafeCommandRunner:
    """在工作区内执行不经过 Shell 的白名单命令。"""

    def __init__(
        self,
        workspace: WorkspaceTools,
        *,
        allowed_commands: Sequence[str],
        timeout: float = 30.0,
        max_output_characters: int = 20_000,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        if max_output_characters < 1:
            raise ValueError("max_output_characters must be at least 1.")

        self.workspace = workspace
        self.allowed_commands = frozenset(
            self._normalize_command(command) for command in allowed_commands
        )
        self.timeout = timeout
        self.max_output_characters = max_output_characters

    async def run_command(
        self,
        command: str,
        arguments: Sequence[str] = (),
        working_directory: str = ".",
    ) -> dict[str, object]:
        normalized = self._normalize_command(command)

        if normalized not in self.allowed_commands:
            raise WorkspaceAccessError(f"Command is not allowed: {command}")

        cwd = self.workspace.resolve_path(working_directory)

        if not cwd.is_dir():
            raise NotADirectoryError("working_directory must be a directory.")

        clean_arguments = tuple(str(argument) for argument in arguments)
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = await asyncio.create_subprocess_exec(
            command,
            *clean_arguments,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creation_flags,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise TimeoutError(f"Command exceeded {self.timeout} seconds.") from None

        stdout_text = stdout.decode(
            "utf-8",
            errors="replace",
        )
        stderr_text = stderr.decode(
            "utf-8",
            errors="replace",
        )

        return {
            "command": command,
            "arguments": list(clean_arguments),
            "working_directory": (self.workspace.relative_path(cwd)),
            "exit_code": process.returncode,
            "stdout": self._truncate(stdout_text),
            "stderr": self._truncate(stderr_text),
        }

    def _truncate(
        self,
        text: str,
    ) -> str:
        if len(text) <= self.max_output_characters:
            return text

        return text[: self.max_output_characters] + "\n...[output truncated]"

    @staticmethod
    def _normalize_command(
        command: str,
    ) -> str:
        clean_command = command.strip()

        if not clean_command:
            raise ValueError("Command cannot be empty.")

        name = Path(clean_command).name.lower()
        name = name.removesuffix(".exe")

        return name
