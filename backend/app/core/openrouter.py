"""Thin client for the OpenRouter chat-completions API.

Shared by the vision material classifier, the destination engine, and the
Reweave Assistant so request/response handling lives in one place.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    """Any failure talking to OpenRouter or reading its response."""


class OpenRouterUnreachable(OpenRouterError):
    """The request never got a response (DNS, timeout, connection reset)."""


class OpenRouterClient:
    def __init__(self, api_key: str, app_title: str = "Reweave", referer: str = "http://localhost:8000"):
        self.api_key = api_key
        self.app_title = app_title
        self.referer = referer

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # -- public API -------------------------------------------------------------

    def complete(self, model: str, messages: list[dict], timeout_s: float = 60, **params: Any) -> str:
        """Blocking completion; returns the assistant message text."""
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(self._body(model, messages, params)).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
            raise OpenRouterError(f"HTTP {exc.code}: {detail}") from exc
        except OSError as exc:  # URLError, timeouts, connection resets
            raise OpenRouterUnreachable(str(exc)) from exc
        except json.JSONDecodeError as exc:
            raise OpenRouterError("OpenRouter returned invalid JSON") from exc
        return self._message_text(payload)

    def complete_json(self, model: str, messages: list[dict], timeout_s: float = 60, **params: Any) -> Any:
        """Blocking completion whose reply is parsed as JSON."""
        return parse_json_reply(self.complete(model, messages, timeout_s=timeout_s, **params))

    async def acomplete(self, model: str, messages: list[dict], timeout_s: float = 30, **params: Any) -> str:
        """Async completion for request handlers that must not block the event loop."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    API_URL,
                    headers=self._headers(),
                    json=self._body(model, messages, params),
                    timeout=timeout_s,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise OpenRouterError(f"OpenRouter error: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise OpenRouterUnreachable(f"Could not reach OpenRouter: {exc}") from exc
        return self._message_text(payload)

    # -- helpers ----------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.app_title,
            "X-OpenRouter-Title": self.app_title,
        }

    @staticmethod
    def _body(model: str, messages: list[dict], params: dict) -> dict:
        return {"model": model, "messages": messages, **params}

    @staticmethod
    def _message_text(payload: dict) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError("Unexpected response from OpenRouter") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content


def parse_json_reply(text: str) -> Any:
    """Parse a model reply as JSON, tolerating prose or code fences around the object."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise OpenRouterError("Model reply was not JSON")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise OpenRouterError("Model reply was not JSON") from exc
