"""HTTP client for OpenAI-compatible and Anthropic-compatible chat APIs.

The client keeps provider differences in one place: endpoint, auth headers,
token-limit field, system-message handling, and response parsing. It does not
use vendor SDKs and never logs an API key.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .registry import PROVIDERS, ModelSpec, ProviderSpec, resolve_model
from .types import ChatMessage, ChatResult, LLMError, MessageLike, Usage

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_ERROR_BODY = 2000
_TOKEN_PATTERN = re.compile(
    r"\b(?:sk|ak|ark|pk)[-_][A-Za-z0-9_-]{6,}\b",
    re.IGNORECASE,
)


class LLMClient:
    """Call registered models through one uniform interface."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        env_path: str | Path | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
        timeout: tuple[float, float] | None = None,
    ) -> None:
        """Create a client.

        Args:
            env: Environment mapping. When omitted, `.env` is loaded and
                `os.environ` is used.
            env_path: Alternative `.env` path.
            session: Shared session for tests or custom transports. When
                omitted, each thread gets its own `requests.Session`.
            sleep: Sleep function, injectable for tests.
            max_attempts: Total attempts per call, including the first one.
            timeout: Optional `(connect, read)` override. Otherwise each
                provider's timeout is used.
        """
        if env is None:
            path = Path(env_path) if env_path is not None else DEFAULT_ENV_PATH
            load_dotenv(dotenv_path=path, override=False)
            env = os.environ
        self._env = env
        self._session = session
        self._sleep = sleep
        self._max_attempts = max(1, max_attempts)
        self._timeout = timeout
        self._local = threading.local()
        self._semaphores = {
            provider_id: threading.Semaphore(max(1, provider.max_concurrency))
            for provider_id, provider in PROVIDERS.items()
        }

    def _get_session(self) -> requests.Session:
        if self._session is not None:
            return self._session
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            self._local.session = session
        return session

    def _api_key(self, provider: ProviderSpec) -> str:
        key = self._env.get(provider.api_key_env, "").strip()
        if not key:
            raise LLMError(
                f"missing API key: set {provider.api_key_env} in .env",
                provider=provider.id,
            )
        return key

    def chat(
        self,
        model: str | ModelSpec,
        messages: str | MessageLike | Sequence[MessageLike],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: str | None = None,
        extra_body: Mapping[str, Any] | None = None,
        include_raw: bool = False,
    ) -> ChatResult:
        """Send one non-streaming chat request.

        Args:
            model: Registry key, model ID, display name, or a `ModelSpec`.
            messages: A prompt string or chat messages. System messages are
                moved to the top-level `system` field for Anthropic.
            max_tokens: Output cap. Defaults to the model's registered value.
            temperature: Sampling temperature. Defaults to the model setting;
                when both are unset the provider default is used.
            reasoning: Optional reasoning level, such as `"high"`. The client
                merges the model's provider-specific reasoning body when one
                is registered for that level.
            extra_body: Provider-specific fields merged into the request.
            include_raw: Keep the full JSON response in `ChatResult.raw`.

        Returns:
            A normalized `ChatResult`.

        Raises:
            LLMError: The provider is missing a key, returns an error, or
                keeps failing after all retry attempts.
        """
        spec = resolve_model(model) if isinstance(model, str) else model
        provider = PROVIDERS[spec.provider]
        api_key = self._api_key(provider)
        normalized = _normalize_messages(messages)
        payload, headers = _build_request(
            spec,
            provider,
            api_key,
            normalized,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning=reasoning,
            extra_body=extra_body,
        )

        started = time.perf_counter()
        response, attempts = self._post_with_retries(provider, headers, payload, spec)
        latency_ms = (time.perf_counter() - started) * 1000
        data = self._decode(response, headers, provider, spec, attempts)

        if provider.api_style == "anthropic":
            result = _parse_anthropic(data, spec, latency_ms, attempts, headers)
        else:
            result = _parse_openai(data, spec, latency_ms, attempts, headers)
        if include_raw:
            result.raw = data
        return result

    def _post_with_retries(
        self,
        provider: ProviderSpec,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        spec: ModelSpec,
    ) -> tuple[requests.Response, int]:
        timeout = self._timeout or provider.timeout
        semaphore = self._semaphores[provider.id]
        with semaphore:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = self._get_session().post(
                        provider.chat_url,
                        headers=dict(headers),
                        json=dict(payload),
                        timeout=timeout,
                    )
                except requests.RequestException as exc:
                    if attempt >= self._max_attempts:
                        raise LLMError(
                            f"request failed after {attempt} attempt(s): {exc}",
                            provider=provider.id,
                            model_key=spec.key,
                            attempts=attempt,
                        ) from exc
                    self._sleep(_backoff(attempt))
                    continue

                if (
                    response.status_code in _RETRY_STATUS
                    and attempt < self._max_attempts
                ):
                    self._sleep(_retry_delay(response, attempt))
                    continue

                if response.status_code != 200:
                    raise LLMError(
                        f"provider returned HTTP {response.status_code}",
                        provider=provider.id,
                        model_key=spec.key,
                        status=response.status_code,
                        body=_error_body(response, headers),
                        attempts=attempt,
                    )
                return response, attempt

            raise LLMError(
                "request failed",
                provider=provider.id,
                model_key=spec.key,
                attempts=self._max_attempts,
            )

    def _decode(
        self,
        response: requests.Response,
        headers: Mapping[str, str],
        provider: ProviderSpec,
        spec: ModelSpec,
        attempts: int,
    ) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError(
                "provider returned a non-JSON response",
                provider=provider.id,
                model_key=spec.key,
                status=response.status_code,
                body=_error_body(response, headers),
                attempts=attempts,
            ) from exc
        if not isinstance(data, dict):
            raise LLMError(
                "provider returned unexpected JSON",
                provider=provider.id,
                model_key=spec.key,
                status=response.status_code,
                body=_truncate(json.dumps(data, ensure_ascii=False)),
                attempts=attempts,
            )
        if (
            data.get("error") is not None
            and not data.get("choices")
            and not data.get("content")
        ):
            raise LLMError(
                "provider returned an error payload",
                provider=provider.id,
                model_key=spec.key,
                status=response.status_code,
                body=_json_error_body(data, headers),
                attempts=attempts,
            )
        return data


def _normalize_messages(
    messages: str | MessageLike | Sequence[MessageLike],
) -> list[dict[str, str]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    if isinstance(messages, Mapping):
        messages = [messages]
    normalized: list[dict[str, str]] = []
    for message in messages:
        if isinstance(message, ChatMessage):
            role, content = message.role, message.content
        elif isinstance(message, Mapping):
            role = message.get("role")
            content = message.get("content")
        else:
            raise TypeError(f"unsupported message type: {type(message).__name__}")
        if not isinstance(role, str) or role not in {
            "system",
            "user",
            "assistant",
            "tool",
        }:
            raise ValueError(f"unsupported role: {role!r}")
        if not isinstance(content, str):
            raise TypeError("message content must be a string")
        normalized.append({"role": role, "content": content})
    if not normalized:
        raise ValueError("messages must not be empty")
    return normalized


def _build_request(
    spec: ModelSpec,
    provider: ProviderSpec,
    api_key: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None,
    temperature: float | None,
    reasoning: str | None,
    extra_body: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    max_value = max_tokens if max_tokens is not None else spec.max_tokens
    if max_value <= 0:
        raise ValueError("max_tokens must be positive")
    chosen_temperature = temperature if temperature is not None else spec.temperature
    if chosen_temperature is not None and not spec.supports_temperature:
        raise ValueError(
            f"{spec.key} only accepts the provider's default temperature"
        )

    body: dict[str, Any] = dict(spec.extra_body)
    if reasoning is not None:
        body.update(spec.reasoning_bodies.get(reasoning, {}))
    if extra_body:
        body.update(extra_body)
    # The token limit is controlled by ModelSpec.max_tokens_field. Drop any
    # duplicate from extra_body so a provider never receives both fields.
    body.pop("max_tokens", None)
    body.pop("max_completion_tokens", None)

    if provider.api_style == "anthropic":
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        chat_messages = [m for m in messages if m["role"] != "system"]
        if not chat_messages:
            raise ValueError("Anthropic requests need a non-system message")
        body["model"] = spec.model_id
        body["max_tokens"] = max_value
        body["messages"] = chat_messages
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "name2smiles-bench/0.1",
        }
    else:
        body["model"] = spec.model_id
        body["messages"] = messages
        body["stream"] = False
        body[spec.max_tokens_field] = max_value
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "name2smiles-bench/0.1",
        }

    if chosen_temperature is not None:
        body["temperature"] = chosen_temperature
    return body, headers


def _parse_openai(
    data: dict[str, Any],
    spec: ModelSpec,
    latency_ms: float,
    attempts: int,
    headers: Mapping[str, str] | None = None,
) -> ChatResult:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError(
            "response has no choices",
            provider=spec.provider,
            model_key=spec.key,
            status=200,
            body=_json_error_body(data, headers),
            attempts=attempts,
        )
    choice = choices[0] if isinstance(choices[0], Mapping) else {}
    message = choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
    return ChatResult(
        model_key=spec.key,
        model_id=spec.model_id,
        provider=spec.provider,
        text=_openai_content_text(message.get("content")),
        reasoning=_text_value(
            message.get("reasoning_content") or message.get("reasoning")
        ),
        finish_reason=choice.get("finish_reason"),
        usage=_openai_usage(data.get("usage")),
        latency_ms=round(latency_ms, 1),
        attempts=attempts,
        response_model=data.get("model"),
        request_id=data.get("id"),
    )


def _parse_anthropic(
    data: dict[str, Any],
    spec: ModelSpec,
    latency_ms: float,
    attempts: int,
    headers: Mapping[str, str] | None = None,
) -> ChatResult:
    blocks = data.get("content")
    if not isinstance(blocks, list):
        raise LLMError(
            "response has no content blocks",
            provider=spec.provider,
            model_key=spec.key,
            status=200,
            body=_json_error_body(data, headers),
            attempts=attempts,
        )

    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        if block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block.get("type") == "thinking":
            reasoning_parts.append(str(block.get("thinking") or ""))

    raw_usage = data.get("usage")
    usage = raw_usage if isinstance(raw_usage, Mapping) else {}
    output_details = usage.get("output_tokens_details")
    output_details = output_details if isinstance(output_details, Mapping) else {}
    input_tokens = _int_or_none(usage.get("input_tokens"))
    output_tokens = _int_or_none(usage.get("output_tokens"))
    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    return ChatResult(
        model_key=spec.key,
        model_id=spec.model_id,
        provider=spec.provider,
        text="".join(text_parts),
        reasoning="".join(reasoning_parts),
        finish_reason=data.get("stop_reason"),
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=_int_or_none(output_details.get("thinking_tokens")),
            cached_input_tokens=_int_or_none(usage.get("cache_read_input_tokens")),
            cache_write_input_tokens=_int_or_none(
                usage.get("cache_creation_input_tokens")
            ),
        ),
        latency_ms=round(latency_ms, 1),
        attempts=attempts,
        response_model=data.get("model"),
        request_id=data.get("id"),
    )


def _openai_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, Mapping) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def _text_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_text_value(item) for item in value)
    if isinstance(value, Mapping):
        for key in ("text", "content", "thinking"):
            if key in value:
                return _text_value(value[key])
    return ""


def _openai_usage(raw: Any) -> Usage:
    if not isinstance(raw, Mapping):
        return Usage()
    details = raw.get("completion_tokens_details")
    details = details if isinstance(details, Mapping) else {}
    output_details = raw.get("output_tokens_details")
    output_details = output_details if isinstance(output_details, Mapping) else {}
    prompt_details = raw.get("prompt_tokens_details")
    prompt_details = prompt_details if isinstance(prompt_details, Mapping) else {}

    input_tokens = raw.get("prompt_tokens")
    if input_tokens is None:
        input_tokens = raw.get("input_tokens")
    output_tokens = raw.get("completion_tokens")
    if output_tokens is None:
        output_tokens = raw.get("output_tokens")

    reasoning_tokens = details.get("reasoning_tokens")
    if reasoning_tokens is None:
        reasoning_tokens = output_details.get("reasoning_tokens")

    cached_tokens = prompt_details.get("cached_tokens")
    if not cached_tokens:
        cached_tokens = raw.get("prompt_cache_hit_tokens")
    if cached_tokens is None:
        cached_tokens = raw.get("cache_read_input_tokens")

    cache_write_tokens = prompt_details.get("cache_write_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = raw.get("cache_creation_input_tokens")

    return Usage(
        input_tokens=_int_or_none(input_tokens),
        output_tokens=_int_or_none(output_tokens),
        total_tokens=_int_or_none(raw.get("total_tokens")),
        reasoning_tokens=_int_or_none(reasoning_tokens),
        cached_input_tokens=_int_or_none(cached_tokens),
        cache_write_input_tokens=_int_or_none(cache_write_tokens),
    )


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response.headers else None
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), 60.0)
        except ValueError:
            pass
    return _backoff(attempt)


def _backoff(attempt: int) -> float:
    return min(2.0 ** (attempt - 1), 30.0) + random.uniform(0.0, 0.5)


def _redact_secrets(
    text: str,
    headers: Mapping[str, str] | None = None,
) -> str:
    if headers:
        for header_name in ("Authorization", "x-api-key"):
            value = headers.get(header_name)
            if not value:
                continue
            secret = value[7:] if value.lower().startswith("bearer ") else value
            if secret:
                text = text.replace(secret, "[redacted]")
    return _TOKEN_PATTERN.sub("[redacted]", text)


def _error_body(
    response: requests.Response,
    headers: Mapping[str, str] | None = None,
) -> str:
    text = getattr(response, "text", "") or ""
    return _truncate(_redact_secrets(text, headers))


def _json_error_body(
    data: Any,
    headers: Mapping[str, str] | None = None,
) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return _truncate(_redact_secrets(text, headers))


def _truncate(text: str, limit: int = _MAX_ERROR_BODY) -> str:
    return text if len(text) <= limit else text[:limit] + "..."
