import asyncio
import json

import pytest
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.services import llm_provider


class _Response:
    status_code = 200

    def __init__(
        self,
        content: str | None,
        *,
        finish_reason: str = "stop",
        reasoning_content: str | None = None,
        completion_tokens: int = 202,
        reasoning_tokens: int | None = None,
    ) -> None:
        self._content = content
        self._finish_reason = finish_reason
        self._reasoning_content = reasoning_content
        self._completion_tokens = completion_tokens
        self._reasoning_tokens = reasoning_tokens
        self.content = json.dumps(self.json(), ensure_ascii=False).encode()

    def json(self):
        usage = {
            "prompt_tokens": 101,
            "completion_tokens": self._completion_tokens,
            "total_tokens": 101 + self._completion_tokens,
        }
        if self._reasoning_tokens is not None:
            usage["completion_tokens_details"] = {
                "reasoning_tokens": self._reasoning_tokens,
            }
        return {
            "choices": [
                {
                    "finish_reason": self._finish_reason,
                    "message": {
                        "content": self._content,
                        "reasoning_content": self._reasoning_content,
                    },
                }
            ],
            "usage": usage,
        }


class _Client:
    responses = []
    calls = []

    def __init__(self, **_kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class _MissingContentResponse(_Response):
    def json(self):
        body = super().json()
        body["choices"][0]["message"].pop("content", None)
        return body


class _ErrorResponse:
    status_code = 400

    def __init__(self) -> None:
        self._body = {
            "error": {
                "message": (
                    "The supported API model names are deepseek-v4-pro or deepseek-v4-flash, "
                    "but you passed deepseek-chat."
                ),
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_request_error",
            }
        }
        self.content = json.dumps(self._body).encode()

    def json(self):
        return self._body


def test_default_deepseek_model_matches_current_api():
    assert Settings.model_fields["deepseek_model"].default == "deepseek-v4-flash"


def test_deepseek_request_contract_uses_supported_model(monkeypatch):
    _Client.calls = []
    _Client.responses = [_Response('{"ok":true}')]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")
    monkeypatch.setattr(llm_provider.settings, "deepseek_model", "deepseek-v4-flash")

    result = asyncio.run(
        llm_provider.LLMProvider().generate_json(
            system="Return valid JSON.",
            payload={"input": "x"},
            max_tokens=8000,
        )
    )

    request = _Client.calls[0][1]["json"]
    assert result == {"ok": True}
    assert request["model"] == "deepseek-v4-flash"
    assert request["messages"] == [
        {"role": "system", "content": "Return valid JSON."},
        {"role": "user", "content": '{"input": "x"}'},
    ]
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 8000
    assert "temperature" not in request
    assert "stream" not in request


def test_deepseek_structured_request_can_disable_thinking(monkeypatch):
    _Client.calls = []
    _Client.responses = [_Response('{"ok":true}')]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    result = asyncio.run(
        llm_provider.LLMProvider().generate_json(
            system="Return JSON only.",
            payload={"input": "x"},
            thinking_mode="disabled",
        )
    )

    assert result == {"ok": True}
    assert _Client.calls[0][1]["json"]["thinking"] == {"type": "disabled"}


def test_real_deepseek_deprecated_model_400_keeps_safe_error_fields(monkeypatch):
    _Client.calls = []
    _Client.responses = [_ErrorResponse()]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")
    monkeypatch.setattr(llm_provider.settings, "deepseek_model", "deepseek-chat")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="Return JSON.", payload={"input": "x"}))

    error = raised.value
    assert error.code == "llm_model_unavailable"
    assert error.http_status == 400
    assert error.retryable is False
    assert json.loads(error.schema_error) == {
        "code": "invalid_request_error",
        "message": (
            "The supported API model names are deepseek-v4-pro or deepseek-v4-flash, "
            "but you passed deepseek-chat."
        ),
        "type": "invalid_request_error",
    }
    assert len(_Client.calls) == 1


def test_invalid_json_is_repaired_exactly_once(monkeypatch):
    _Client.calls = []
    _Client.responses = [_Response('{"topic": "broken"'), _Response('{"topic": "repaired"}')]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    result = asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert result == {"topic": "repaired"}
    assert len(_Client.calls) == 2
    assert _Client.calls[1][1]["json"]["messages"][0]["content"].startswith("修复下面")


def test_invalid_json_after_single_repair_returns_structured_diagnostic(monkeypatch):
    _Client.calls = []
    _Client.responses = [_Response("not-json"), _Response("still-not-json")]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_response_parse_failed"
    assert raised.value.response_length == len("still-not-json")
    assert raised.value.schema_error
    assert len(_Client.calls) == 2


def test_rate_limit_retries_once_with_backoff(monkeypatch):
    limited = _Response('{"error":"rate"}')
    limited.status_code = 429
    _Client.calls = []
    _Client.responses = [limited, _Response('{"ok":true}')]
    sleep = AsyncMock()
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.asyncio, "sleep", sleep)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    result = asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert result == {"ok": True}
    assert len(_Client.calls) == 2
    sleep.assert_awaited_once_with(1)


def test_balance_error_is_distinct_and_not_retried(monkeypatch):
    insufficient = _Response('{"error":"balance"}')
    insufficient.status_code = 402
    _Client.calls = []
    _Client.responses = [insufficient]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_balance_insufficient"
    assert raised.value.retryable is False
    assert len(_Client.calls) == 1


def test_timeout_retries_once_then_fails_explicitly(monkeypatch):
    _Client.calls = []
    _Client.responses = [llm_provider.httpx.ReadTimeout("slow"), llm_provider.httpx.ReadTimeout("slow")]
    sleep = AsyncMock()
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.asyncio, "sleep", sleep)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_timeout"
    assert len(_Client.calls) == 2
    sleep.assert_awaited_once_with(1)


def test_connection_failure_retries_once_then_fails_explicitly(monkeypatch):
    _Client.calls = []
    _Client.responses = [llm_provider.httpx.ConnectError("offline"), llm_provider.httpx.ConnectError("offline")]
    sleep = AsyncMock()
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.asyncio, "sleep", sleep)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_network_error"
    assert len(_Client.calls) == 2
    sleep.assert_awaited_once_with(1)


def test_generic_http_error_is_explicit_and_not_retried(monkeypatch):
    failure = _Response('{"error":"bad request"}')
    failure.status_code = 422
    _Client.calls = []
    _Client.responses = [failure]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_http_error"
    assert raised.value.http_status == 422
    assert len(_Client.calls) == 1


def test_finish_reason_length_is_never_accepted_as_complete(monkeypatch, caplog):
    _Client.calls = []
    _Client.responses = [_Response('{"ok":true}', finish_reason="length")]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(llm_provider.LLMProvider().generate_json(system="json", payload={"input": "x"}))

    assert raised.value.code == "llm_response_truncated"
    assert raised.value.schema_error == "finish_reason=length"
    assert "finish_reason=length" in caplog.text
    assert "truncated=True" in caplog.text
    assert "prompt_tokens=101" in caplog.text
    assert "completion_tokens=202" in caplog.text
    assert "total_tokens=303" in caplog.text


def test_empty_content_records_reasoning_usage_separately(monkeypatch, caplog):
    _Client.calls = []
    _Client.responses = [
        _Response(
            None,
            finish_reason="length",
            reasoning_content="内部推理" * 100,
            completion_tokens=8000,
            reasoning_tokens=7990,
        )
    ]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(
            llm_provider.LLMProvider().generate_json(
                system="json",
                payload={"input": "x"},
                thinking_mode="disabled",
            )
        )

    error = raised.value
    assert error.code == "llm_empty_content"
    assert error.content_length == 0
    assert error.reasoning_content_length == len("内部推理" * 100)
    assert error.completion_tokens == 8000
    assert error.reasoning_tokens == 7990
    assert error.schema_error == "finish_reason=length;content=empty"
    assert "reasoning_tokens=7990" in caplog.text
    assert f"reasoning_content_length={len('内部推理' * 100)}" in caplog.text
    assert "thinking_mode=disabled" in caplog.text


@pytest.mark.parametrize(
    ("response", "expected_type"),
    [
        (_Response(None), "null"),
        (_Response(""), "str"),
        (_MissingContentResponse(None), "missing"),
    ],
)
def test_http_200_empty_content_is_classified_without_json_parse(monkeypatch, response, expected_type):
    _Client.calls = []
    _Client.responses = [response]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(
            llm_provider.LLMProvider().generate_json(
                system="json",
                payload={"input": "x"},
                allow_format_repair=False,
                thinking_mode="disabled",
            )
        )

    assert raised.value.code == "llm_empty_content"
    assert raised.value.content_type == expected_type
    assert raised.value.content_length == 0
    assert len(_Client.calls) == 1


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"ok": true}\n```',
        '以下是结果：\n{"ok": true}\n以上。',
    ],
)
def test_safe_parser_repairs_wrapping_without_model_call(monkeypatch, caplog, content):
    _Client.calls = []
    _Client.responses = [_Response(content)]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    result = asyncio.run(
        llm_provider.LLMProvider().generate_json(
            system="json",
            payload={"input": "x"},
            allow_format_repair=False,
            thinking_mode="disabled",
        )
    )

    assert result == {"ok": True}
    assert len(_Client.calls) == 1
    assert "parser_repair_applied=True" in caplog.text


def test_nonempty_malformed_json_reports_safe_metadata(monkeypatch):
    _Client.calls = []
    malformed = '{"rewrite":{"script":"正文"},"rank":01}'
    _Client.responses = [_Response(malformed)]
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "deepseek")
    monkeypatch.setattr(llm_provider.settings, "deepseek_api_key", "sk-preview-test")

    with pytest.raises(llm_provider.LLMProviderError) as raised:
        asyncio.run(
            llm_provider.LLMProvider().generate_json(
                system="json",
                payload={"input": "x"},
                allow_format_repair=False,
                thinking_mode="disabled",
            )
        )

    error = raised.value
    assert error.code == "llm_json_parse_error"
    assert error.content_type == "str"
    assert error.content_length == len(malformed)
    assert error.finish_reason == "stop"
    assert error.parser_repair_applied is True
    assert len(_Client.calls) == 1


def test_pipeline_failure_contract_contains_request_fields():
    result = llm_provider.safe_parse_json_response('```json\n{"ok": true,}\n```')
    assert result == {"ok": True}
