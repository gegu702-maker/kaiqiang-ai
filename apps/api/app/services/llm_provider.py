from __future__ import annotations

import asyncio
import ast
import json
import logging
import re
import time
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)


def _safe_upstream_error(response: httpx.Response) -> str:
    """Return only bounded, non-request fields from an upstream error envelope."""
    try:
        body = response.json()
    except ValueError:
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return ""

    details: dict[str, str] = {}
    for field in ("type", "code", "param", "message"):
        value = error.get(field)
        if value is None:
            continue
        text = str(value)
        text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [REDACTED]", text)
        text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}", "sk-[REDACTED]", text)
        details[field] = text[:300]
    return json.dumps(details, ensure_ascii=False, sort_keys=True)


def _model_is_unavailable(upstream_error: str) -> bool:
    normalized = upstream_error.lower()
    return "model" in normalized and (
        "supported api model names" in normalized
        or "model not exist" in normalized
        or "model_not_found" in normalized
    )


class LLMProviderError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool,
        http_status: int | None = None,
        response_length: int = 0,
        schema_error: str = "",
        content_length: int = 0,
        reasoning_content_length: int = 0,
        completion_tokens: int | None = None,
        reasoning_tokens: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.http_status = http_status
        self.response_length = response_length
        self.schema_error = schema_error
        self.content_length = content_length
        self.reasoning_content_length = reasoning_content_length
        self.completion_tokens = completion_tokens
        self.reasoning_tokens = reasoning_tokens


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return fence.group(1).strip() if fence else text


def _extract_json_object(value: str) -> str:
    text = _strip_code_fence(value)
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    end = text.rfind("}")
    return text[start : end + 1] if end > start else text


def _remove_trailing_commas(value: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", value)


def safe_parse_json_response(raw: str) -> dict[str, Any]:
    """Parse model JSON with tolerance for common chat-model formatting noise."""
    candidates: list[str] = []
    extracted = _extract_json_object(raw)
    for candidate in (raw, _strip_code_fence(raw), extracted, _remove_trailing_commas(extracted)):
        candidate = candidate.strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as error:
            last_error = error
        else:
            if isinstance(data, dict):
                return data

    python_literal = _remove_trailing_commas(extracted).strip()
    try:
        data = ast.literal_eval(python_literal)
    except (SyntaxError, ValueError) as error:
        last_error = error
    else:
        if isinstance(data, dict):
            return data

    detail = str(last_error or "unknown JSON error")
    raise ValueError(f"Model response did not contain a usable JSON object: {detail}") from last_error


class LLMProvider:
    async def generate_json(
        self,
        *,
        system: str,
        payload: dict[str, Any],
        max_tokens: int = 8000,
        attempt_label: str = "initial",
        max_transport_attempts: int = 2,
        allow_format_repair: bool = True,
        thinking_mode: str | None = None,
    ) -> dict[str, Any]:
        provider = settings.llm_provider.lower()
        if provider == "deepseek":
            return await self._chat_json(
                base_url=settings.deepseek_base_url.rstrip("/"),
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                system=system,
                payload=payload,
                provider_name="DeepSeek",
                max_tokens=max_tokens,
                attempt_label=attempt_label,
                max_transport_attempts=max_transport_attempts,
                allow_format_repair=allow_format_repair,
                thinking_mode=thinking_mode,
            )
        if provider == "openai":
            return await self._chat_json(
                base_url="https://api.openai.com",
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                system=system,
                payload=payload,
                provider_name="OpenAI",
                max_tokens=max_tokens,
                attempt_label=attempt_label,
                max_transport_attempts=max_transport_attempts,
                allow_format_repair=allow_format_repair,
                thinking_mode=None,
            )
        if provider == "mock":
            return self._mock(payload)
        raise HTTPException(status_code=500, detail=f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    async def _chat_json(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system: str,
        payload: dict[str, Any],
        provider_name: str,
        max_tokens: int,
        attempt_label: str,
        max_transport_attempts: int,
        allow_format_repair: bool,
        thinking_mode: str | None,
    ) -> dict[str, Any]:
        request_id = current_request_id()
        if not api_key:
            raise LLMProviderError(
                code="llm_credentials_missing",
                message=f"{provider_name} API Key 未配置。",
                retryable=False,
            )

        async def request_completion(messages: list[dict[str, str]], *, attempt: str) -> tuple[str, int, str]:
            request_body_chars = len(json.dumps(messages, ensure_ascii=False))
            response: httpx.Response | None = None
            transport_limit = max(1, max_transport_attempts)
            for transport_attempt in range(1, transport_limit + 1):
                transport_label = (
                    attempt
                    if transport_limit == 1
                    else f"{attempt}_{transport_attempt}"
                )
                attempt_started = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15)) as client:
                        request_json: dict[str, Any] = {
                            "model": model,
                            "max_tokens": max_tokens,
                            "response_format": {"type": "json_object"},
                            "messages": messages,
                        }
                        if provider_name == "DeepSeek" and thinking_mode is not None:
                            if thinking_mode not in {"enabled", "disabled"}:
                                raise ValueError(f"Unsupported DeepSeek thinking mode: {thinking_mode}")
                            request_json["thinking"] = {"type": thinking_mode}
                        response = await client.post(
                            f"{base_url}/v1/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}"},
                            json=request_json,
                        )
                except httpx.TimeoutException as error:
                    logger.warning(
                        "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=timeout "
                        "http_status=none response_length=0 finish_reason=none truncated=false "
                        "max_tokens=%s prompt_tokens=none completion_tokens=none total_tokens=none request_body_chars=%s elapsed_ms=%s",
                        request_id,
                        provider_name,
                        model,
                        transport_label,
                        max_tokens,
                        request_body_chars,
                        round((time.perf_counter() - attempt_started) * 1000),
                    )
                    if transport_attempt < transport_limit:
                        await asyncio.sleep(1)
                        continue
                    timeout_message = (
                        "AI 服务调用超时，受控重试后仍失败。"
                        if transport_limit > 1
                        else "AI 服务调用超时。"
                    )
                    raise LLMProviderError(code="llm_timeout", message=timeout_message, retryable=True) from error
                except httpx.HTTPError as error:
                    logger.warning(
                        "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=network_error type=%s "
                        "http_status=none response_length=0 finish_reason=none truncated=false "
                        "max_tokens=%s prompt_tokens=none completion_tokens=none total_tokens=none request_body_chars=%s elapsed_ms=%s",
                        request_id,
                        provider_name,
                        model,
                        transport_label,
                        type(error).__name__,
                        max_tokens,
                        request_body_chars,
                        round((time.perf_counter() - attempt_started) * 1000),
                    )
                    if transport_attempt < transport_limit:
                        await asyncio.sleep(1)
                        continue
                    network_message = (
                        "AI 服务连接中断，受控重试后仍失败。"
                        if transport_limit > 1
                        else "AI 服务连接中断。"
                    )
                    raise LLMProviderError(code="llm_network_error", message=network_message, retryable=True) from error

                response_length = len(response.content)
                if response.status_code < 400:
                    break
                upstream_error = _safe_upstream_error(response)
                if response.status_code == 400 and _model_is_unavailable(upstream_error):
                    code, message, retryable = "llm_model_unavailable", f"配置的 AI 模型 {model} 当前不可用。", False
                elif response.status_code == 429:
                    code, message, retryable = "llm_rate_limited", "AI 服务请求过于频繁。", True
                elif response.status_code == 402:
                    code, message, retryable = "llm_balance_insufficient", "AI 服务余额不足。", False
                elif response.status_code in {408, 504}:
                    code, message, retryable = "llm_upstream_timeout", "AI 服务上游处理超时。", True
                elif response.status_code in {401, 403}:
                    code, message, retryable = "llm_auth_error", "AI 服务凭据无效或无权限。", False
                else:
                    code, message, retryable = "llm_http_error", f"AI 服务返回 HTTP {response.status_code}。", response.status_code >= 500
                logger.warning(
                    "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=http_error code=%s "
                    "http_status=%s response_length=%s finish_reason=none truncated=false max_tokens=%s "
                    "prompt_tokens=none completion_tokens=none total_tokens=none request_body_chars=%s elapsed_ms=%s upstream_error=%r",
                    request_id,
                    provider_name,
                    model,
                    transport_label,
                    code,
                    response.status_code,
                    response_length,
                    max_tokens,
                    request_body_chars,
                    round((time.perf_counter() - attempt_started) * 1000),
                    upstream_error,
                )
                if retryable and transport_attempt < transport_limit:
                    await asyncio.sleep(1)
                    continue
                suffix = "，受控重试后仍失败。" if retryable and transport_attempt == transport_limit and transport_limit > 1 else ""
                raise LLMProviderError(
                    code=code,
                    message=f"{message.rstrip('。')}{suffix or '。'}",
                    retryable=retryable,
                    http_status=response.status_code,
                    response_length=response_length,
                    schema_error=upstream_error,
                )

            if response is None:
                raise LLMProviderError(code="llm_network_error", message="AI 服务未返回响应。", retryable=True)
            response_length = len(response.content)
            try:
                body = response.json()
                usage = body.get("usage") if isinstance(body, dict) else {}
                usage = usage if isinstance(usage, dict) else {}
                choice = body["choices"][0]
                message = choice["message"]
                raw_value = message.get("content")
                reasoning_value = message.get("reasoning_content")
                raw = "" if raw_value is None else raw_value
                reasoning_content = reasoning_value if isinstance(reasoning_value, str) else ""
                finish_reason = str(choice.get("finish_reason") or "")
                if not isinstance(raw, str):
                    raise TypeError("message.content is not a string")
            except (ValueError, KeyError, IndexError, TypeError) as error:
                diagnostic = f"{type(error).__name__}: {error}"[:300]
                logger.warning(
                    "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=envelope_error "
                    "http_status=%s response_length=%s finish_reason=none truncated=false max_tokens=%s "
                    "prompt_tokens=none completion_tokens=none total_tokens=none schema_error=%r",
                    request_id,
                    provider_name,
                    model,
                    attempt,
                    response.status_code,
                    response_length,
                    max_tokens,
                    diagnostic,
                )
                raise LLMProviderError(
                    code="llm_response_schema_error",
                    message="AI 响应格式错误。",
                    retryable=True,
                    http_status=response.status_code,
                    response_length=response_length,
                    schema_error=diagnostic,
                ) from error
            completion_details = usage.get("completion_tokens_details")
            completion_details = completion_details if isinstance(completion_details, dict) else {}
            completion_tokens = usage.get("completion_tokens")
            completion_tokens = completion_tokens if isinstance(completion_tokens, int) else None
            reasoning_tokens = completion_details.get("reasoning_tokens")
            reasoning_tokens = reasoning_tokens if isinstance(reasoning_tokens, int) else None
            logger.warning(
                "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=received http_status=%s "
                "response_length=%s finish_reason=%s truncated=%s max_tokens=%s prompt_tokens=%s "
                "completion_tokens=%s reasoning_tokens=%s total_tokens=%s request_body_chars=%s "
                "content_length=%s reasoning_content_length=%s thinking_mode=%s elapsed_ms=%s",
                request_id,
                provider_name,
                model,
                attempt,
                response.status_code,
                response_length,
                finish_reason,
                finish_reason == "length",
                max_tokens,
                usage.get("prompt_tokens", "none"),
                usage.get("completion_tokens", "none"),
                reasoning_tokens if reasoning_tokens is not None else "none",
                usage.get("total_tokens", "none"),
                request_body_chars,
                len(raw),
                len(reasoning_content),
                thinking_mode or "provider_default",
                round((time.perf_counter() - attempt_started) * 1000),
            )
            if finish_reason == "length":
                empty_content = not raw.strip()
                raise LLMProviderError(
                    code="llm_empty_content_exhausted" if empty_content else "llm_response_truncated",
                    message=(
                        "AI 响应输出预算已耗尽，未产生最终正文。"
                        if empty_content
                        else "AI 响应达到输出上限，结果已截断。"
                    ),
                    retryable=True,
                    http_status=response.status_code,
                    response_length=response_length,
                    schema_error=(
                        "finish_reason=length;content=empty"
                        if empty_content
                        else "finish_reason=length"
                    ),
                    content_length=len(raw),
                    reasoning_content_length=len(reasoning_content),
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                )
            return raw, response.status_code, finish_reason

        raw, http_status, finish_reason = await request_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            attempt=attempt_label,
        )
        try:
            return safe_parse_json_response(raw)
        except ValueError as initial_error:
            initial_schema_error = str(initial_error)[:300]
            logger.warning(
                "viral_llm request_id=%s provider=%s model=%s attempt=initial outcome=parse_error http_status=%s content_length=%s finish_reason=%s schema_error=%r",
                request_id,
                provider_name,
                model,
                http_status,
                len(raw),
                finish_reason,
                initial_schema_error,
            )

        if not allow_format_repair:
            raise LLMProviderError(
                code="llm_json_contract_error",
                message="AI 响应不符合 JSON 契约。",
                retryable=False,
                http_status=http_status,
                response_length=len(raw),
                schema_error=initial_schema_error,
            )

        repaired_raw, repaired_status, repaired_finish = await request_completion(
            [
                {
                    "role": "system",
                    "content": "修复下面的模型输出，使其成为语义不变、完整且可解析的 JSON 对象。只输出 JSON；不得解释或补造事实。",
                },
                {"role": "user", "content": raw},
            ],
            attempt=f"{attempt_label}_format_repair",
        )
        try:
            return safe_parse_json_response(repaired_raw)
        except ValueError as repair_error:
            schema_error = str(repair_error)[:300]
            logger.warning(
                "viral_llm request_id=%s provider=%s model=%s attempt=format_repair outcome=parse_error http_status=%s content_length=%s finish_reason=%s schema_error=%r",
                request_id,
                provider_name,
                model,
                repaired_status,
                len(repaired_raw),
                repaired_finish,
                schema_error,
            )
            raise LLMProviderError(
                code="llm_response_parse_failed",
                message="AI 响应格式错误，自动修复一次后仍无法解析。",
                retryable=True,
                http_status=repaired_status,
                response_length=len(repaired_raw),
                schema_error=schema_error,
            ) from repair_error

    def _mock(self, payload: dict[str, Any]) -> dict[str, Any]:
        product_name = payload.get("product_name", "商品")
        highlights = payload.get("product_highlights", "核心卖点")
        hook = f"别急着下单，{product_name}真正值得看的，是这几个细节。"
        script = f"{hook} {highlights}。如果你正在挑选同类产品，先看使用场景，再看细节，最后再决定适不适合你。"
        return {
            "narration_script": script,
            "hook": hook,
            "selling_points": [
                {"index": 1, "point": highlights, "consumer_benefit": "降低选择成本", "proof_angle": "真实场景演示"}
            ],
            "scene_prompts": [
                {
                    "index": 1,
                    "duration": "0-15s",
                    "scene": "商品图开场并展示卖点",
                    "camera": "慢推近景",
                    "action": "商品居中，字幕强化卖点",
                    "narration": script,
                    "visual_prompt": f"{product_name} 电商短视频，9:16，清晰商品主体，电影感光影",
                    "tool_suggestion": "FFmpeg",
                }
            ],
            "subtitle_text": script,
            "title_options": [f"{product_name}到底值不值得买？", f"别乱买，先看{product_name}这几点"],
            "caption": f"{product_name} AI 带货视频脚本",
            "cover_text": "别急着买",
            "cover_prompt": f"{product_name} 电商封面，强对比，大字标题",
            "hashtags": [f"#{product_name}", "#AI带货视频"],
            "comment_prompt": "你会因为哪个卖点下单？",
            "closing_cta": "先看详情，再决定是否入手。",
            "admin_workflow": [{"step": 1, "tool": "FFmpeg", "action": "自动合成视频并导出 MP4"}],
        }
