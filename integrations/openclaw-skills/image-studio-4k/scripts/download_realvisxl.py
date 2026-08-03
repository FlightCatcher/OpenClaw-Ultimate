"""Reliably download and verify the RealVisXL checkpoint, then hot-cache it."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "SG161222/RealVisXL_V5.0"
FILENAME = "RealVisXL_V5.0_fp16.safetensors"
EXPECTED_BYTES = 6_938_065_488
EXPECTED_SHA256 = "6a35a7855770ae9820a3c931d4964c3817b6d9e3c6f9c4dabb5b3a94e5643b80"
LIBRARY_DIR = Path(r"E:\OpenClaw-Knowledge\models\image")
HOT_CACHE_DIR = Path(r"D:\AI-Models-HotCache\Models\checkpoints")
HOT_CACHE = HOT_CACHE_DIR / FILENAME


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path) -> None:
    if path.stat().st_size != EXPECTED_BYTES:
        raise RuntimeError(f"Size mismatch: {path.stat().st_size} != {EXPECTED_BYTES}")
    actual = sha256(path)
    if actual != EXPECTED_SHA256:
        raise RuntimeError(f"SHA-256 mismatch: {actual}")


def main() -> None:
    HOT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = Path(
        hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            local_dir=HOT_CACHE_DIR,
        )
    )
    verify(downloaded)
    print(f"Verified hot cache: {downloaded}", flush=True)

    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    external_master = LIBRARY_DIR / FILENAME
    if not external_master.exists() or external_master.stat().st_size != EXPECTED_BYTES:
        temporary = external_master.with_suffix(external_master.suffix + ".part")
        shutil.copy2(downloaded, temporary)
        verify(temporary)
        temporary.replace(external_master)
    else:
        verify(external_master)
    print(f"Verified external master: {external_master}", flush=True)


if __name__ == "__main__":
    main()
