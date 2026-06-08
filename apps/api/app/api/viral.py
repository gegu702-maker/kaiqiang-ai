from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_authenticated_user, get_bearer_token
from app.core.supabase import get_supabase
from app.services.viral_analyzer import analyze_viral_script

router = APIRouter(prefix="/viral", tags=["viral"])


class ViralAnalyzeRequest(BaseModel):
    source_url: str = Field(default="", max_length=2000)
    raw_script: str = Field(default="", max_length=6000)
    industry: str
    language: str = "zh"


@router.post("/analyze")
async def analyze_viral(
    payload: ViralAnalyzeRequest,
    token: str = Depends(get_bearer_token),
    supabase: Client = Depends(get_supabase),
) -> dict:
    user = get_authenticated_user(supabase, token)
    return await analyze_viral_script(
        supabase,
        user_id=user["id"],
        email=user["email"],
        source_url=payload.source_url,
        raw_script=payload.raw_script,
        industry=payload.industry,
        language=payload.language,
    )
