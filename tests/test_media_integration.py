from __future__ import annotations

from pathlib import Path

from openclaw_ultimate.integrations.media import OllamaVisionClient
from openclaw_ultimate.tools import WorkspaceTools


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"response": "识别到 VELA"}


def test_local_vision_client_reads_only_workspace_image(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = tmp_path / "sample.png"
    image.write_bytes(b"not-a-real-image")
    captured = {}

    def fake_post(url, *, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "openclaw_ultimate.integrations.media.httpx.post",
        fake_post,
    )
    client = OllamaVisionClient(
        workspace=WorkspaceTools(tmp_path),
        base_url="http://127.0.0.1:11434",
        model="vision",
    )

    result = client.analyze("sample.png", prompt="OCR")

    assert result.text == "识别到 VELA"
    assert result.path == "sample.png"
    assert captured["json"]["images"]
