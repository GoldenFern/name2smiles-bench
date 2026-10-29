import json

import pytest

from name2smiles.llm import (
    DEFAULT_MAX_TOKENS,
    LLMClient,
    LLMError,
    MODELS,
    PROVIDERS,
    resolve_model,
    validate_registry,
)


CANDIDATE_KEYS = {
    "deepseek-v4-pro",
    "deepseek-flash",
    "glm-5.3",
    "glm-5.3-flash",
    "minimax-m3.1-flash",
    "longcat-2.5-preview",
    "mimo-v2.6-flash",
    "mimo-v2.6-pro",
    "kimi-k2.6",
    "kimi-k3.1-pro",
    "qwen3.8-flash",
    "qwen3.8-max",
    "gpt-6-astra",
    "gpt-6.1-sol",
    "gpt-6.1-terra",
    "gpt-6-luna",
    "claude-opus-5.5",
    "claude-haiku-5.5",
    "gemini-4-argon",
    "gemini-3.8-flash",
}


def test_default_output_cap():
    assert DEFAULT_MAX_TOKENS == 50_000
    assert all(spec.max_tokens == 50_000 for spec in MODELS.values())


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict | None = None,
        text: str | None = None,
        headers: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.headers = headers or {}

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs: object) -> object:
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def openai_payload(
    text: str = "Hi",
    reasoning: str = "",
    finish_reason: str = "stop",
) -> dict:
    return {
        "id": "chatcmpl-test",
        "model": "test-model",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text,
                    "reasoning_content": reasoning,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "completion_tokens_details": {"reasoning_tokens": 2},
            "prompt_tokens_details": {
                "cached_tokens": 3,
                "cache_write_tokens": 1,
            },
        },
    }


def anthropic_payload() -> dict:
    return {
        "id": "msg_test",
        "model": "claude-opus-5-5",
        "content": [
            {"type": "thinking", "thinking": "think"},
            {"type": "text", "text": "Hi"},
            {"type": "text", "text": " there"},
        ],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 7,
            "output_tokens_details": {"thinking_tokens": 4},
            "cache_read_input_tokens": 2,
            "cache_creation_input_tokens": 3,
        },
    }


def test_registry_has_all_candidates_and_is_valid():
    validate_registry()
    assert set(MODELS) == CANDIDATE_KEYS
    assert PROVIDERS["kimi"].max_concurrency == 1


def test_every_model_has_low_and_high_reasoning():
    for key, spec in MODELS.items():
        assert "low" in spec.reasoning_bodies, key
        assert "high" in spec.reasoning_bodies, key


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("deepseek v4 pro", "deepseek-v4-pro"),
        ("DeepSeek V4 Pro", "deepseek-v4-pro"),
        ("deepseek_v4_pro", "deepseek-v4-pro"),
        ("glm 5.3 flash", "glm-5.3-flash"),
        ("MiniMax-M3.1-Flash", "minimax-m3.1-flash"),
        ("kimi k3.1 pro", "kimi-k3.1-pro"),
        ("claude opus 5.5", "claude-opus-5.5"),
        ("gemini 4 argon", "gemini-4-argon"),
    ],
)
def test_resolve_model(name: str, expected: str):
    assert resolve_model(name).key == expected


def test_openai_request_and_response():
    spec = resolve_model("deepseek-v4-pro")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    result = client.chat("deepseek v4 pro", "hi", max_tokens=1234)

    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == provider.chat_url
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == spec.model_id
    assert kwargs["json"]["max_tokens"] == 1234
    assert "max_completion_tokens" not in kwargs["json"]
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert "temperature" not in kwargs["json"]

    assert result.text == "Hi"
    assert result.reasoning == ""
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.usage.reasoning_tokens == 2
    assert result.usage.cached_input_tokens == 3
    assert result.usage.cache_write_input_tokens == 1
    assert result.attempts == 1
    assert result.raw is None


def test_deepseek_cache_hit_tokens_are_used():
    spec = resolve_model("deepseek-v4-pro")
    provider = PROVIDERS[spec.provider]
    payload = openai_payload()
    payload["usage"]["prompt_tokens_details"] = {}
    payload["usage"]["prompt_cache_hit_tokens"] = 7
    session = FakeSession([FakeResponse(payload=payload)])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    result = client.chat(spec, "hi")

    assert result.usage.cached_input_tokens == 7


def test_single_message_mapping_is_accepted():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, {"role": "user", "content": "hi"})

    assert session.calls[0][1]["json"]["messages"] == [
        {"role": "user", "content": "hi"}
    ]


def test_gpt_uses_max_completion_tokens():
    spec = resolve_model("gpt-6-astra")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi")

    payload = session.calls[0][1]["json"]
    assert payload["max_completion_tokens"] == spec.max_tokens
    assert "max_tokens" not in payload


def test_mimo_uses_max_completion_tokens():
    spec = resolve_model("mimo-v2.6-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi")

    payload = session.calls[0][1]["json"]
    assert payload["max_completion_tokens"] == spec.max_tokens
    assert "max_tokens" not in payload


def test_anthropic_request_and_response():
    spec = resolve_model("claude-opus-5.5")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=anthropic_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    result = client.chat(
        spec,
        [
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hi"},
        ],
    )

    url, kwargs = session.calls[0]
    assert url == provider.chat_url
    assert kwargs["headers"]["x-api-key"] == "test-key"
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["json"]["system"] == "be concise"
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert kwargs["json"]["max_tokens"] == spec.max_tokens
    assert "temperature" not in kwargs["json"]

    assert result.text == "Hi there"
    assert result.reasoning == "think"
    assert result.finish_reason == "end_turn"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 7
    assert result.usage.total_tokens == 19
    assert result.usage.reasoning_tokens == 4
    assert result.usage.cached_input_tokens == 2
    assert result.usage.cache_write_input_tokens == 3


@pytest.mark.parametrize(
    "model_key",
    ["kimi-k2.6", "kimi-k3.1-pro", "claude-opus-5.5", "claude-haiku-5.5"],
)
def test_temperature_unsupported_raises(model_key: str):
    spec = resolve_model(model_key)
    provider = PROVIDERS[spec.provider]
    session = FakeSession([])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    with pytest.raises(ValueError, match="default temperature"):
        client.chat(spec, "hi", temperature=0.2)

    assert session.calls == []


def test_temperature_override_is_sent():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", temperature=0.2)

    assert session.calls[0][1]["json"]["temperature"] == 0.2


def test_high_reasoning_body_for_deepseek():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="high")

    payload = session.calls[0][1]["json"]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"


def test_high_reasoning_body_for_claude():
    spec = resolve_model("claude-haiku-5.5")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=anthropic_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="high")

    payload = session.calls[0][1]["json"]
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"] == {"effort": "high"}


def test_high_reasoning_body_for_qwen():
    spec = resolve_model("qwen3.8-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="high")

    payload = session.calls[0][1]["json"]
    assert payload["enable_thinking"] is True
    assert payload["thinking_budget"] == 8192


def test_low_reasoning_keeps_deepseek_thinking():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="low")

    payload = session.calls[0][1]["json"]
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "low"


def test_low_reasoning_body_for_claude():
    spec = resolve_model("claude-haiku-5.5")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=anthropic_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="low")

    payload = session.calls[0][1]["json"]
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"] == {"effort": "low"}


def test_low_reasoning_body_for_qwen():
    spec = resolve_model("qwen3.8-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="low")

    payload = session.calls[0][1]["json"]
    assert payload["enable_thinking"] is True
    assert payload["thinking_budget"] == 1024


def test_unknown_reasoning_level_adds_nothing():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    client.chat(spec, "hi", reasoning="medium")

    payload = session.calls[0][1]["json"]
    assert "thinking" not in payload
    assert "reasoning_effort" not in payload


def test_retries_on_rate_limit():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    session = FakeSession(
        [
            FakeResponse(
                status_code=429,
                payload={"error": "slow down"},
                headers={"Retry-After": "0"},
            ),
            FakeResponse(payload=openai_payload()),
        ]
    )
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
        max_attempts=2,
    )

    result = client.chat(spec, "hi")

    assert len(session.calls) == 2
    assert result.attempts == 2


def test_provider_concurrency_override():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=FakeSession([]),
        provider_concurrency={"deepseek": 5},
    )

    assert client._semaphores["deepseek"]._value == 5
    assert (
        client._semaphores["zhipu"]._value == PROVIDERS["zhipu"].max_concurrency
    )


def test_missing_key_raises_without_network():
    spec = resolve_model("deepseek-flash")
    session = FakeSession([])
    client = LLMClient(env={}, session=session, sleep=lambda _: None)

    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        client.chat(spec, "hi")

    assert session.calls == []


def test_http_error_includes_status_and_body():
    spec = resolve_model("glm-5.3")
    provider = PROVIDERS[spec.provider]
    session = FakeSession(
        [
            FakeResponse(
                status_code=400,
                payload={"error": "bad request"},
                text='{"error": "bad request"}',
            )
        ]
    )
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
        max_attempts=1,
    )

    with pytest.raises(LLMError) as exc_info:
        client.chat(spec, "hi")

    assert exc_info.value.status == 400
    assert "bad request" in str(exc_info.value)


def test_error_body_redacts_keys():
    spec = resolve_model("kimi-k3.1-pro")
    provider = PROVIDERS[spec.provider]
    secret = "sk-test-secret-123456"
    session = FakeSession(
        [
            FakeResponse(
                status_code=400,
                payload={"error": "bad"},
                text=f"bad key {secret} and ak-abcdef123456",
            )
        ]
    )
    client = LLMClient(
        env={provider.api_key_env: secret},
        session=session,
        sleep=lambda _: None,
        max_attempts=1,
    )

    with pytest.raises(LLMError) as exc_info:
        client.chat(spec, "hi")

    message = str(exc_info.value)
    assert secret not in message
    assert "ak-abcdef123456" not in message
    assert "[redacted]" in message


def test_error_payload_redacts_keys():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    secret = "sk-test-secret-123456"
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload={"error": f"bad key {secret}"},
            )
        ]
    )
    client = LLMClient(
        env={provider.api_key_env: secret},
        session=session,
        sleep=lambda _: None,
        max_attempts=1,
    )

    with pytest.raises(LLMError, match="error payload") as exc_info:
        client.chat(spec, "hi")

    assert secret not in str(exc_info.value)
    assert "[redacted]" in str(exc_info.value)


def test_non_json_response_raises():
    spec = resolve_model("glm-5.3")
    provider = PROVIDERS[spec.provider]
    session = FakeSession(
        [FakeResponse(status_code=200, payload=None, text="<html>oops</html>")]
    )
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
        max_attempts=1,
    )

    with pytest.raises(LLMError, match="non-JSON"):
        client.chat(spec, "hi")


def test_include_raw_and_to_dict():
    spec = resolve_model("deepseek-v4-pro")
    provider = PROVIDERS[spec.provider]
    session = FakeSession([FakeResponse(payload=openai_payload())])
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=session,
        sleep=lambda _: None,
    )

    result = client.chat(spec, "hi", include_raw=True)
    data = result.to_dict()

    assert data["raw"]["id"] == "chatcmpl-test"
    assert data["usage"]["input_tokens"] == 10
    assert data["model_key"] == "deepseek-v4-pro"


def test_empty_message_list_is_rejected():
    spec = resolve_model("deepseek-flash")
    provider = PROVIDERS[spec.provider]
    client = LLMClient(
        env={provider.api_key_env: "test-key"},
        session=FakeSession([]),
        sleep=lambda _: None,
    )

    with pytest.raises(ValueError, match="must not be empty"):
        client.chat(spec, [])
