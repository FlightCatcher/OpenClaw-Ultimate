from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


class LifeIntegrationError(RuntimeError):
    """A life-service connector could not complete a request."""


class LifeConfigurationError(ValueError):
    """A life-service connector has unsafe or incomplete configuration."""


@dataclass(frozen=True, slots=True)
class HomeAssistantEntity:
    entity_id: str
    state: str
    attributes: dict[str, Any]
    last_changed: str | None = None


class HomeAssistantClient:
    """Small authenticated client for the official Home Assistant REST API."""

    _entity_pattern = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise LifeConfigurationError("Home Assistant URL must be an HTTP(S) origin.")
        if not token.strip():
            raise LifeConfigurationError("Home Assistant access token cannot be empty.")
        if timeout <= 0:
            raise LifeConfigurationError("Home Assistant timeout must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {
            "Authorization": f"Bearer {token.strip()}",
            "Content-Type": "application/json",
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def health(self) -> dict[str, Any]:
        result = self._request("GET", "/api/")
        return result if isinstance(result, dict) else {"message": str(result)}

    def list_states(self, domain: str | None = None) -> tuple[HomeAssistantEntity, ...]:
        clean_domain = domain.strip().casefold() if domain else None
        payload = self._request("GET", "/api/states")
        if not isinstance(payload, list):
            raise LifeIntegrationError("Home Assistant states response is not a list.")
        entities = tuple(self._parse_entity(item) for item in payload if isinstance(item, dict))
        if clean_domain:
            prefix = f"{clean_domain}."
            entities = tuple(item for item in entities if item.entity_id.startswith(prefix))
        return entities

    def get_state(self, entity_id: str) -> HomeAssistantEntity:
        clean_entity = self._validate_entity_id(entity_id)
        payload = self._request("GET", f"/api/states/{clean_entity}")
        if not isinstance(payload, dict):
            raise LifeIntegrationError("Home Assistant entity response is not an object.")
        return self._parse_entity(payload)

    def call_service(
        self,
        *,
        domain: str,
        service: str,
        entity_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> tuple[HomeAssistantEntity, ...]:
        clean_domain = self._validate_segment(domain, "domain")
        clean_service = self._validate_segment(service, "service")
        request_data = dict(data or {})
        if entity_id:
            request_data["entity_id"] = self._validate_entity_id(entity_id)
        payload = self._request(
            "POST",
            f"/api/services/{clean_domain}/{clean_service}",
            json=request_data,
        )
        if not isinstance(payload, list):
            raise LifeIntegrationError("Home Assistant service response is not a list.")
        return tuple(self._parse_entity(item) for item in payload if isinstance(item, dict))

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LifeIntegrationError(
                f"Home Assistant request failed: {method} {path}"
            ) from exc

    @classmethod
    def _validate_entity_id(cls, value: str) -> str:
        clean_value = value.strip().casefold()
        if not cls._entity_pattern.fullmatch(clean_value):
            raise LifeConfigurationError("Invalid Home Assistant entity_id.")
        return clean_value

    @staticmethod
    def _validate_segment(value: str, label: str) -> str:
        clean_value = value.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_]+", clean_value):
            raise LifeConfigurationError(f"Invalid Home Assistant {label}.")
        return clean_value

    @staticmethod
    def _parse_entity(payload: dict[str, Any]) -> HomeAssistantEntity:
        entity_id = str(payload.get("entity_id", "")).strip()
        if not entity_id:
            raise LifeIntegrationError("Home Assistant entity has no entity_id.")
        attributes = payload.get("attributes", {})
        return HomeAssistantEntity(
            entity_id=entity_id,
            state=str(payload.get("state", "unknown")),
            attributes=dict(attributes) if isinstance(attributes, dict) else {},
            last_changed=(
                str(payload["last_changed"]) if payload.get("last_changed") is not None else None
            ),
        )


class WeComWebhookClient:
    """Outbound-only official WeCom group robot webhook connector."""

    def __init__(
        self,
        *,
        webhook_url: str,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(webhook_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "qyapi.weixin.qq.com"
            or parsed.path != "/cgi-bin/webhook/send"
            or not parsed.query
        ):
            raise LifeConfigurationError("Invalid official WeCom webhook URL.")
        if timeout <= 0:
            raise LifeConfigurationError("WeCom timeout must be greater than zero.")
        self.webhook_url = webhook_url
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def send_text(self, content: str) -> dict[str, Any]:
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("WeCom message cannot be empty.")
        if len(clean_content) > 4_000:
            raise ValueError("WeCom message is too long.")
        try:
            response = self._client.post(
                self.webhook_url,
                json={"msgtype": "text", "text": {"content": clean_content}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LifeIntegrationError("WeCom webhook request failed.") from exc
        if not isinstance(payload, dict) or int(payload.get("errcode", -1)) != 0:
            raise LifeIntegrationError("WeCom rejected the message.")
        return {"ok": True, "platform": "wecom", "message": "sent"}


class QQBotClient:
    """Outbound text client for the official QQ Bot v2 OpenAPI."""

    token_url = "https://api.bot.qq.com/app/getAppAccessToken"
    api_base_url = "https://api.bot.qq.com"

    def __init__(
        self,
        *,
        app_id: str,
        client_secret: str,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        if not app_id.strip() or not client_secret.strip():
            raise LifeConfigurationError("QQ Bot AppID and ClientSecret are required.")
        if timeout <= 0:
            raise LifeConfigurationError("QQ Bot timeout must be greater than zero.")
        self.app_id = app_id.strip()
        self._client_secret = client_secret.strip()
        self.timeout = timeout
        self._clock = clock
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def send_text(
        self,
        *,
        target_type: str,
        target_openid: str,
        content: str,
    ) -> dict[str, Any]:
        clean_type = target_type.strip().casefold()
        if clean_type not in {"user", "group"}:
            raise LifeConfigurationError("QQ target_type must be 'user' or 'group'.")
        clean_target = target_openid.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", clean_target):
            raise LifeConfigurationError("Invalid QQ target OpenID.")
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("QQ message cannot be empty.")
        if len(clean_content) > 2_000:
            raise ValueError("QQ message is too long.")

        resource = "users" if clean_type == "user" else "groups"
        token = self._get_access_token()
        try:
            response = self._client.post(
                f"{self.api_base_url}/v2/{resource}/{clean_target}/messages",
                headers={
                    "Authorization": f"QQBot {token}",
                    "Content-Type": "application/json",
                },
                json={"msg_type": 0, "content": clean_content},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LifeIntegrationError("QQ Bot message request failed.") from exc
        if not isinstance(payload, dict) or not payload.get("id"):
            raise LifeIntegrationError("QQ Bot returned an invalid message response.")
        return {
            "ok": True,
            "platform": "qq",
            "message_id": str(payload["id"]),
            "timestamp": payload.get("timestamp"),
        }

    def _get_access_token(self) -> str:
        now = float(self._clock())
        if self._access_token and now < self._access_token_expires_at:
            return self._access_token
        try:
            response = self._client.post(
                self.token_url,
                json={"appId": self.app_id, "clientSecret": self._client_secret},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LifeIntegrationError("QQ Bot authentication failed.") from exc
        if not isinstance(payload, dict) or not str(payload.get("access_token", "")).strip():
            raise LifeIntegrationError("QQ Bot returned no access token.")
        token = str(payload["access_token"]).strip()
        expires_in = max(60, int(payload.get("expires_in", 7200)))
        self._access_token = token
        self._access_token_expires_at = now + max(1, expires_in - 60)
        return token
