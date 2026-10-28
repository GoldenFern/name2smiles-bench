"""Shared types for LLM provider calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    """One chat message with a text payload."""

    role: str
    content: str


MessageLike = ChatMessage | Mapping[str, str]


@dataclass
class Usage:
    """Normalized token usage across providers."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return asdict(self)


@dataclass
class ChatResult:
    """One completed chat call."""

    model_key: str
    model_id: str
    provider: str
    text: str
    reasoning: str
    finish_reason: str | None
    usage: Usage
    latency_ms: float
    attempts: int
    response_model: str | None = None
    request_id: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.raw is None:
            data.pop("raw", None)
        return data


class LLMError(RuntimeError):
    """A provider call failed.

    The API key is never stored or included in the message. Only the
    environment variable name is reported by the client.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model_key: str | None = None,
        status: int | None = None,
        body: str | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model_key = model_key
        self.status = status
        self.body = body
        self.attempts = attempts

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.provider:
            parts.append(f"provider={self.provider}")
        if self.model_key:
            parts.append(f"model={self.model_key}")
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.body:
            parts.append(f"body={self.body[:1000]}")
        return " | ".join(parts)
