from __future__ import annotations

from typing import Any

from app.services.content_ai import generate_commerce_package
from app.services.llm_provider import LLMProvider


STYLE_LABELS = {
    "hard_sell": "硬核带货",
    "emotional_seed": "情绪种草",
    "premium": "高端质感",
    "factory_boss": "工厂老板风",
    "tiktok": "TikTok 风格",
    "review": "测评解说",
    "story": "剧情短片",
}


async def generate_video_script(
    *,
    product_name: str,
    product_highlights: str,
    target_audience: str,
    video_style: str,
    max_seconds: int,
    use_digital_human: bool,
) -> dict[str, Any]:
    style_label = STYLE_LABELS.get(video_style, STYLE_LABELS.get("hard_sell", "硬核带货"))
    prompt = {
        "product_name": product_name,
        "product_highlights": product_highlights,
        "target_audience": target_audience,
        "video_style": style_label,
        "max_seconds": max_seconds,
        "requirements": [
            "生成 15 到 45 秒 AI 带货短视频脚本",
            "必须包含开场 hook、产品卖点、行动引导",
            "旁白口语化、适合抖音/TikTok",
            "输出 JSON，不要 markdown",
        ],
        "schema": {
            "narration_script": "完整旁白",
            "hook": "黄金 3 秒开头",
            "selling_points": [{"index": 1, "point": "", "consumer_benefit": "", "proof_angle": ""}],
            "scene_prompts": [{"index": 1, "duration": "0-3s", "scene": "", "camera": "", "action": "", "narration": "", "visual_prompt": "", "tool_suggestion": ""}],
            "subtitle_text": "字幕文本",
            "title_options": ["标题1", "标题2", "标题3"],
            "caption": "发布文案",
            "cover_text": "封面大字",
            "cover_prompt": "封面图 prompt",
            "hashtags": ["#标签"],
            "comment_prompt": "评论区引导",
            "closing_cta": "成交收口",
            "admin_workflow": [{"step": 1, "tool": "FFmpeg", "action": ""}],
        },
    }

    data = await LLMProvider().generate_json(
        system="你是短视频带货导演和商业编导。只输出合法 JSON。",
        payload=prompt,
    )

    fallback = generate_commerce_package(
        product_name=product_name,
        product_highlights=product_highlights,
        target_audience=target_audience,
        video_style="hard_sell" if video_style not in {"hard_sell", "emotional_seed", "review", "story"} else video_style,
        use_digital_human=use_digital_human,
    )
    narration = str(data.get("narration_script") or data.get("subtitle_text") or fallback["script"]).strip()
    return {
        "selling_points": data.get("selling_points") or fallback["selling_points"],
        "hook": data.get("hook") or fallback["hook"],
        "script": narration,
        "narration_script": narration,
        "shot_list": data.get("scene_prompts") or fallback["shot_list"],
        "scene_prompts": data.get("scene_prompts") or fallback["shot_list"],
        "subtitle_text": data.get("subtitle_text") or narration,
        "title_options": data.get("title_options") or fallback["title_options"],
        "caption": data.get("caption") or fallback["caption"],
        "cover_text": data.get("cover_text") or fallback["cover_text"],
        "cover_prompt": data.get("cover_prompt") or fallback["cover_prompt"],
        "hashtags": data.get("hashtags") or fallback["hashtags"],
        "comment_prompt": data.get("comment_prompt") or fallback["comment_prompt"],
        "closing_cta": data.get("closing_cta") or fallback["closing_cta"],
        "admin_workflow": data.get("admin_workflow") or fallback["admin_workflow"],
    }
