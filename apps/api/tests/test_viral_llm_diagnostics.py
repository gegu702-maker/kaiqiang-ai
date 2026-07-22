import asyncio
import json

import pytest
from unittest.mock import AsyncMock

from app.services import llm_provider


class _Response:
    status_code = 200

    def __init__(self, content: str, *, finish_reason: str = "stop") -> None:
        self._content = content
        self._finish_reason = finish_reason
        self.content = json.dumps(self.json(), ensure_ascii=False).encode()

    def json(self):
        return {
            "choices": [
                {
                    "finish_reason": self._finish_reason,
                    "message": {"content": self._content},
                }
            ]
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
        return self.responses.pop(0)


def test_invalid_json_is_repaired_exactly_once(monkeypatch):
    _Client.calls = []
    _Client.responses = [_Response('{"topic": "broken"', finish_reason="length"), _Response('{"topic": "repaired"}')]
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


def test_pipeline_failure_contract_contains_request_fields():
    result = llm_provider.safe_parse_json_response('```json\n{"ok": true,}\n```')
    assert result == {"ok": True}
