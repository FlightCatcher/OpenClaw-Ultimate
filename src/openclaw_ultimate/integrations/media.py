from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from openclaw_ultimate.tools.workspace import WorkspaceTools


@dataclass(frozen=True, slots=True)
class ImageAnalysis:
    model: str
    path: str
    text: str


class OllamaVisionClient:
    """Analyze a workspace image with a local Ollama vision model."""

    allowed_suffixes = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})

    def __init__(
        self,
        *,
        workspace: WorkspaceTools,
        base_url: str,
        model: str,
        timeout: float = 300.0,
        max_image_bytes: int = 20_000_000,
    ) -> None:
        self.workspace = workspace
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout = timeout
        self.max_image_bytes = max_image_bytes
        if not self.model:
            raise ValueError("Vision model cannot be empty.")

    def analyze(
        self,
        path: str,
        *,
        prompt: str = "请描述这张图片，并准确识别其中可见的文字。",
    ) -> ImageAnalysis:
        target = self.workspace.resolve_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Image does not exist: {path}")
        if target.suffix.casefold() not in self.allowed_suffixes:
            raise ValueError(f"Unsupported image type: {target.suffix}")
        raw = target.read_bytes()
        if len(raw) > self.max_image_bytes:
            raise ValueError(f"Image exceeds {self.max_image_bytes} bytes.")
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt.strip(),
                "images": [base64.b64encode(raw).decode("ascii")],
                "stream": False,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), str):
            raise TypeError("Ollama vision response is invalid.")
        return ImageAnalysis(
            model=self.model,
            path=self.workspace.relative_path(target),
            text=payload["response"].strip(),
        )


@dataclass(frozen=True, slots=True)
class Transcript:
    path: str
    text: str


class WhisperCliClient:
    """Optional local whisper.cpp-compatible command adapter."""

    def __init__(
        self,
        *,
        workspace: WorkspaceTools,
        executable: str,
        model_path: Path,
        timeout: float = 600.0,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.model_path = model_path
        self.timeout = timeout

    def transcribe(self, path: str) -> Transcript:
        target = self.workspace.resolve_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Audio does not exist: {path}")
        result = subprocess.run(
            [
                self.executable,
                "-m",
                str(self.model_path),
                "-f",
                str(target),
                "--output-txt",
                "--no-prints",
            ],
            cwd=self.workspace.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            shell=False,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Whisper transcription failed.")
        transcript_path = Path(f"{target}.txt")
        text = transcript_path.read_text(encoding="utf-8").strip()
        return Transcript(
            path=self.workspace.relative_path(target),
            text=text,
        )
