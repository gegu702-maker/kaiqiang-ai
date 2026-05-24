from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings


class LLMProvider:
    async def generate_json(self, *, system: str, payload: dict[str, Any]) -> dict[str, Any]:
        provider = settings.llm_provider.lower()
        if provider == "deepseek":
            return await self._chat_json(
                base_url=settings.deepseek_base_url.rstrip("/"),
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                system=system,
                payload=payload,
                provider_name="DeepSeek",
            )
        if provider == "openai":
            return await self._chat_json(
                base_url="https://api.openai.com",
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                system=system,
                payload=payload,
                provider_name="OpenAI",
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
    ) -> dict[str, Any]:
        if not api_key:
            raise HTTPException(status_code=500, detail=f"{provider_name} API Key 未配置，无法生成 AI 文本。")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                },
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"{provider_name} generation failed: {response.text}")

        raw = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=502, detail=f"{provider_name} returned invalid JSON: {raw[:500]}") from error

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
