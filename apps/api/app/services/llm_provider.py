from __future__ import annotations

import asyncio
import ast
import json
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.viral_diagnostics import current_request_id


logger = logging.getLogger(__name__)


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
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.http_status = http_status
        self.response_length = response_length
        self.schema_error = schema_error


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
    async def generate_json(self, *, system: str, payload: dict[str, Any], max_tokens: int = 6000) -> dict[str, Any]:
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
            for transport_attempt in range(1, 3):
                attempt_label = f"{attempt}_{transport_attempt}"
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15)) as client:
                        response = await client.post(
                            f"{base_url}/v1/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}"},
                            json={
                                "model": model,
                                "max_tokens": max_tokens,
                                "response_format": {"type": "json_object"},
                                "messages": messages,
                            },
                        )
                except httpx.TimeoutException as error:
                    logger.warning(
                        "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=timeout request_body_chars=%s max_tokens=%s",
                        request_id,
                        provider_name,
                        model,
                        attempt_label,
                        request_body_chars,
                        max_tokens,
                    )
                    if transport_attempt == 1:
                        await asyncio.sleep(1)
                        continue
                    raise LLMProviderError(code="llm_timeout", message="AI 服务调用超时，重试一次后仍失败。", retryable=True) from error
                except httpx.HTTPError as error:
                    logger.warning(
                        "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=network_error type=%s request_body_chars=%s max_tokens=%s",
                        request_id,
                        provider_name,
                        model,
                        attempt_label,
                        type(error).__name__,
                        request_body_chars,
                        max_tokens,
                    )
                    if transport_attempt == 1:
                        await asyncio.sleep(1)
                        continue
                    raise LLMProviderError(code="llm_network_error", message="AI 服务连接中断，重试一次后仍失败。", retryable=True) from error

                response_length = len(response.content)
                if response.status_code < 400:
                    break
                if response.status_code == 429:
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
                    "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=http_error code=%s http_status=%s request_body_chars=%s max_tokens=%s response_length=%s",
                    request_id,
                    provider_name,
                    model,
                    attempt_label,
                    code,
                    response.status_code,
                    request_body_chars,
                    max_tokens,
                    response_length,
                )
                if retryable and transport_attempt == 1:
                    await asyncio.sleep(1)
                    continue
                suffix = "，重试一次后仍失败。" if retryable and transport_attempt == 2 else ""
                raise LLMProviderError(
                    code=code,
                    message=f"{message.rstrip('。')}{suffix or '。'}",
                    retryable=retryable,
                    http_status=response.status_code,
                    response_length=response_length,
                )

            if response is None:
                raise LLMProviderError(code="llm_network_error", message="AI 服务未返回响应。", retryable=True)
            response_length = len(response.content)
            try:
                body = response.json()
                choice = body["choices"][0]
                raw = choice["message"]["content"]
                finish_reason = str(choice.get("finish_reason") or "")
                if not isinstance(raw, str):
                    raise TypeError("message.content is not a string")
            except (ValueError, KeyError, IndexError, TypeError) as error:
                diagnostic = f"{type(error).__name__}: {error}"[:300]
                logger.warning(
                    "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=envelope_error http_status=%s response_length=%s schema_error=%r",
                    request_id,
                    provider_name,
                    model,
                    attempt,
                    response.status_code,
                    response_length,
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
            logger.warning(
                "viral_llm request_id=%s provider=%s model=%s attempt=%s outcome=received http_status=%s request_body_chars=%s max_tokens=%s response_length=%s content_length=%s finish_reason=%s",
                request_id,
                provider_name,
                model,
                attempt,
                response.status_code,
                request_body_chars,
                max_tokens,
                response_length,
                len(raw),
                finish_reason,
            )
            return raw, response.status_code, finish_reason

        raw, http_status, finish_reason = await request_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            attempt="initial",
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

        repaired_raw, repaired_status, repaired_finish = await request_completion(
            [
                {
                    "role": "system",
                    "content": "修复下面的模型输出，使其成为语义不变、完整且可解析的 JSON 对象。只输出 JSON；不得解释或补造事实。",
                },
                {"role": "user", "content": raw},
            ],
            attempt="format_repair",
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
