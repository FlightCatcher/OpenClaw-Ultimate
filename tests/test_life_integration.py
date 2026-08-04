from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.config import Settings
from openclaw_ultimate.governance import ConfirmationRequired, RiskLevel
from openclaw_ultimate.integrations.life import (
    HomeAssistantClient,
    LifeConfigurationError,
    QQBotClient,
    WeComWebhookClient,
)


def test_home_assistant_reads_and_filters_entities() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "light.living_room",
                    "state": "on",
                    "attributes": {"friendly_name": "客厅灯"},
                    "last_changed": "2026-08-04T00:00:00Z",
                },
                {
                    "entity_id": "vacuum.xiaomi",
                    "state": "docked",
                    "attributes": {"friendly_name": "扫地机器人"},
                },
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = HomeAssistantClient(
            base_url="http://homeassistant.local:8123",
            token="secret-token",
            client=http_client,
        )
        entities = client.list_states("light")

    assert len(entities) == 1
    assert entities[0].entity_id == "light.living_room"
    assert entities[0].attributes["friendly_name"] == "客厅灯"
    assert requests[0].url.path == "/api/states"


def test_home_assistant_calls_service_with_validated_target() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/services/light/turn_on"
        assert json.loads(request.content) == {
            "brightness_pct": 30,
            "entity_id": "light.bedroom",
        }
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "light.bedroom",
                    "state": "on",
                    "attributes": {"brightness": 76},
                }
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = HomeAssistantClient(
            base_url="http://127.0.0.1:8123",
            token="token",
            client=http_client,
        )
        changed = client.call_service(
            domain="light",
            service="turn_on",
            entity_id="light.bedroom",
            data={"brightness_pct": 30},
        )

    assert changed[0].state == "on"


def test_home_assistant_rejects_invalid_entity_id() -> None:
    client = HomeAssistantClient(
        base_url="http://127.0.0.1:8123",
        token="token",
    )
    try:
        with pytest.raises(LifeConfigurationError, match="entity_id"):
            client.get_state("../../secrets")
    finally:
        client.close()


def test_wecom_uses_only_official_webhook_and_sends_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "qyapi.weixin.qq.com"
        assert json.loads(request.content) == {
            "msgtype": "text",
            "text": {"content": "任务已完成"},
        }
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WeComWebhookClient(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
            client=http_client,
        )
        result = client.send_text("任务已完成")

    assert result == {"ok": True, "platform": "wecom", "message": "sent"}


def test_wecom_rejects_non_official_webhook() -> None:
    with pytest.raises(LifeConfigurationError, match="official WeCom"):
        WeComWebhookClient(webhook_url="https://example.com/cgi-bin/webhook/send?key=stolen")


def test_qq_bot_authenticates_and_sends_official_group_message() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/app/getAppAccessToken":
            assert json.loads(request.content) == {
                "appId": "app-123",
                "clientSecret": "secret-456",
            }
            return httpx.Response(200, json={"access_token": "access-token", "expires_in": 7200})
        assert request.url.path == "/v2/groups/GROUP_123/messages"
        assert request.headers["Authorization"] == "QQBot access-token"
        assert json.loads(request.content) == {"msg_type": 0, "content": "VELA 任务已完成"}
        return httpx.Response(
            200,
            json={"id": "message-1", "timestamp": "2026-08-04T10:00:00+08:00"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = QQBotClient(
            app_id="app-123",
            client_secret="secret-456",
            client=http_client,
            clock=lambda: 100.0,
        )
        first = client.send_text(
            target_type="group",
            target_openid="GROUP_123",
            content="VELA 任务已完成",
        )
        client.send_text(
            target_type="group",
            target_openid="GROUP_123",
            content="VELA 任务已完成",
        )

    assert first["message_id"] == "message-1"
    assert len([item for item in requests if item.url.path == "/app/getAppAccessToken"]) == 1


def test_qq_bot_rejects_arbitrary_target_type() -> None:
    client = QQBotClient(app_id="app", client_secret="secret")
    try:
        with pytest.raises(LifeConfigurationError, match="target_type"):
            client.send_text(
                target_type="personal-account",
                target_openid="TARGET_123",
                content="hello",
            )
    finally:
        client.close()


def test_home_control_requires_confirmation_before_network(tmp_path: Path) -> None:
    agent = build_default_agent(
        _life_settings(
            tmp_path,
            home_assistant_enabled=True,
            home_assistant_token="home-secret",
            home_assistant_read_only=False,
        )
    )

    with pytest.raises(ConfirmationRequired) as required:
        asyncio.run(
            agent.tools.get("home_call_service").invoke(
                {
                    "domain": "light",
                    "service": "turn_off",
                    "entity_id": "light.bedroom",
                }
            )
        )

    assert required.value.request.risk == RiskLevel.REVERSIBLE
    assert required.value.request.action == "home.light.turn_off"


def test_wecom_send_requires_confirmation_before_network(tmp_path: Path) -> None:
    agent = build_default_agent(
        _life_settings(
            tmp_path,
            wecom_enabled=True,
            wecom_webhook_url=(
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=not-a-real-key"
            ),
        )
    )

    with pytest.raises(ConfirmationRequired) as required:
        asyncio.run(
            agent.tools.get("send_wecom_message").invoke({"content": "任务已完成"})
        )

    assert required.value.request.risk == RiskLevel.HIGH
    assert required.value.request.action == "message.wecom.send"


def _life_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "workspace_root": tmp_path,
        "governance_db_path": tmp_path / "governance.db",
        "openclaw_enabled": False,
        "comfyui_enabled": False,
        "mcp_enabled": False,
        "knowledge_enabled": False,
        "vision_enabled": False,
        "whisper_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)
