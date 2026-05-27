from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class AvatarTemplate:
    id: str
    name: str
    description: str
    avatar_image: str
    voice_type: str
    gender: str
    style: str
    vip_only: bool = False


AVATAR_TEMPLATES: tuple[AvatarTemplate, ...] = (
    AvatarTemplate(
        id="business_female_01",
        name="商务女主播",
        description="适合知识口播、课程介绍、商业内容",
        avatar_image="/avatars/business_female_01.png",
        voice_type="BV001_streaming",
        gender="female",
        style="business",
    ),
    AvatarTemplate(
        id="business_male_01",
        name="商务男主播",
        description="适合老板IP、财经、商业观点",
        avatar_image="/avatars/business_male_01.png",
        voice_type="BV002_streaming",
        gender="male",
        style="business",
    ),
    AvatarTemplate(
        id="ai_female_01",
        name="AI女主播",
        description="适合AI资讯、科技口播、产品介绍",
        avatar_image="/avatars/ai_female_01.png",
        voice_type="BV001_streaming",
        gender="female",
        style="tech",
    ),
)

_TEMPLATES_BY_ID = {template.id: template for template in AVATAR_TEMPLATES}


def get_avatar_template(template_id: str | None) -> AvatarTemplate:
    selected = (template_id or "business_female_01").strip()
    template = _TEMPLATES_BY_ID.get(selected)
    if not template:
        raise HTTPException(status_code=400, detail="Invalid avatar_template_id")
    return template


def avatar_template_public_url(template: AvatarTemplate) -> str:
    origin = settings.public_site_url.rstrip("/") or settings.web_origin.rstrip("/")
    return f"{origin}{template.avatar_image}"


def avatar_template_dict(template: AvatarTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "avatar_image": template.avatar_image,
        "voice_type": template.voice_type,
        "gender": template.gender,
        "style": template.style,
        "vip_only": template.vip_only,
    }
