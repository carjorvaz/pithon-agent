"""Dependency-free OpenAI-compatible provider with DeepSeek defaults."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """A provider request or response violated the API contract."""


@dataclass(frozen=True)
class Completion:
    message: dict[str, Any]
    usage: dict[str, int]


class ChatProvider(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Completion:
        """Return one assistant message and normalized usage metrics."""


class DeepSeekProvider:
    """Small Chat Completions client using only urllib and json."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        thinking: bool = True,
        reasoning_effort: str = "high",
        timeout: float = 180.0,
        max_tokens: int = 8192,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if reasoning_effort not in {"high", "max"}:
            raise ValueError("reasoning_effort must be high or max")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 32768:
            raise ValueError("max_tokens must be between 1 and 32768")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Completion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
            "max_tokens": self.max_tokens,
        }
        if self.thinking:
            payload["reasoning_effort"] = self.reasoning_effort
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "pithon-agent/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode("utf-8", errors="replace")
            raise ProviderError(f"provider HTTP {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            raise ProviderError(f"provider connection failed: {error}") from error

        try:
            document = json.loads(raw)
            message = document["choices"][0]["message"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ProviderError("provider returned an invalid Chat Completions response") from error
        self._validate_message(message)
        usage = self._normalize_usage(document.get("usage", {}))
        return Completion(message=dict(message), usage=usage)

    @staticmethod
    def _validate_message(message: Any) -> None:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ProviderError("provider response is missing an assistant message")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ProviderError("assistant content must be text or null")
        tool_calls = message.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            raise ProviderError("assistant tool_calls must be a list or null")

    @staticmethod
    def _normalize_usage(usage: Any) -> dict[str, int]:
        if not isinstance(usage, dict):
            return {}
        names = (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
        return {
            name: value
            for name in names
            if isinstance((value := usage.get(name)), int) and not isinstance(value, bool)
        }
