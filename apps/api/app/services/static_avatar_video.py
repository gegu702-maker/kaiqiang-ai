from __future__ import annotations

import math
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes

logger = logging.getLogger(__name__)


async def render_static_avatar_video(
    supabase: Client,
    *,
    audio_url: str,
    subtitle_text: str,
    avatar_image_url: str | None = None,
    duration: float | None = None,
) -> str:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=True) as client:
        audio_response = await client.get(audio_url)
        audio_response.raise_for_status()
        audio_bytes = audio_response.content
    avatar_bytes = await _fetch_optional_avatar_image(avatar_image_url)

    duration_seconds = max(1.0, float(duration or 5.0))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        background_path = tmp_path / "avatar.png"
        audio_path = tmp_path / "voice.mp3"
        output_path = tmp_path / "static-avatar.mp4"

        _build_avatar_background(background_path, subtitle_text, avatar_bytes)
        audio_path.write_bytes(audio_bytes)

        cmd = [
            settings.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-framerate",
            "12",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
            "-t",
            f"{duration_seconds:.3f}",
            "-r",
            "12",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-g",
            "24",
            "-bf",
            "0",
            "-threads",
            "1",
            "-x264-params",
            "rc-lookahead=0:sync-lookahead=0:ref=1:no-mbtree=1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=45)
        except subprocess.TimeoutExpired as error:
            raise HTTPException(status_code=504, detail="FFmpeg static avatar render timed out") from error
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "FFmpeg static avatar render failed",
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "output_exists": output_path.exists(),
                    "output_size": output_path.stat().st_size if output_path.exists() else 0,
                },
            )

        video_bytes = output_path.read_bytes()

    try:
        return upload_public_bytes(
            supabase,
            settings.supabase_video_bucket,
            video_bytes,
            "debug/static-avatar",
            ".mp4",
            "video/mp4",
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail={
                "success": False,
                "error": "storage_upload_failed",
                "message": f"Storage 上传失败：{error}",
            },
        ) from error


async def _fetch_optional_avatar_image(avatar_image_url: str | None) -> bytes | None:
    if not avatar_image_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0), follow_redirects=True) as client:
            response = await client.get(avatar_image_url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as error:
        logger.warning("Static avatar image unavailable; using generated fallback avatar. url=%s error=%s", avatar_image_url, error)
        return None


async def package_dynamic_avatar_video(
    supabase: Client,
    *,
    dynamic_video_url: str,
    audio_url: str,
    subtitle_text: str,
    task_id: str,
    duration: float | None = None,
) -> str:
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        video_response = await client.get(dynamic_video_url)
        video_response.raise_for_status()
        audio_response = await client.get(audio_url)
        audio_response.raise_for_status()

    duration_seconds = max(1.0, float(duration or 5.0))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dynamic_path = tmp_path / "dynamic.mp4"
        audio_path = tmp_path / "voice.mp3"
        overlay_path = tmp_path / "subtitle_overlay.png"
        output_path = tmp_path / "final.mp4"

        dynamic_path.write_bytes(video_response.content)
        audio_path.write_bytes(audio_response.content)
        _build_subtitle_overlay(overlay_path, subtitle_text)

        cmd = [
            settings.ffmpeg_path,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(dynamic_path),
            "-i",
            str(audio_path),
            "-loop",
            "1",
            "-i",
            str(overlay_path),
            "-t",
            f"{duration_seconds:.3f}",
            "-filter_complex",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v0];[v0][2:v]overlay=0:0:format=auto[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-r",
            "25",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg dynamic avatar package failed: {result.stderr[-1200:]}")
        video_bytes = output_path.read_bytes()

    return upload_public_bytes(
        supabase,
        settings.supabase_video_bucket,
        video_bytes,
        f"debug/liveportrait-final/{task_id}",
        ".mp4",
        "video/mp4",
    )


def _build_avatar_background(output_path: Path, subtitle_text: str, avatar_bytes: bytes | None = None) -> None:
    width, height = 1080, 1920
    canvas = Image.new("RGB", (width, height), "#05070d")
    draw = ImageDraw.Draw(canvas)

    for y in range(height):
        shade = int(10 + y / height * 18)
        draw.line([(0, y), (width, y)], fill=(5, 7 + shade // 4, 13 + shade))

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((170, 260, 910, 1000), fill=(49, 215, 255, 34))
    glow_draw.ellipse((280, 390, 800, 910), fill=(183, 248, 113, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow)
    draw = ImageDraw.Draw(canvas)

    avatar_box = (270, 390, 810, 930)
    draw.ellipse(avatar_box, fill=(14, 20, 35), outline=(70, 90, 120), width=3)
    if avatar_bytes:
        _paste_avatar_image(canvas, avatar_bytes, avatar_box)
        draw = ImageDraw.Draw(canvas)
    else:
        draw.ellipse((340, 460, 740, 860), fill=(28, 36, 56), outline=(49, 215, 255), width=4)
        draw.ellipse((440, 585, 480, 625), fill=(230, 238, 248))
        draw.ellipse((600, 585, 640, 625), fill=(230, 238, 248))
        draw.arc((430, 640, 650, 760), 18, 162, fill=(183, 248, 113), width=8)
    draw.rounded_rectangle((380, 890, 700, 1120), radius=70, fill=(17, 24, 39), outline=(70, 90, 120), width=2)

    title_font = _font(54)
    label_font = _font(32)
    small_font = _font(26)
    draw.text((width // 2, 150), "KAIQIANG AI", anchor="mm", fill=(255, 255, 255), font=title_font)
    draw.text((width // 2, 215), "数字人口播", anchor="mm", fill=(49, 215, 255), font=label_font)
    draw.text((width // 2, 1210), "AI Digital Human", anchor="mm", fill=(210, 222, 240), font=label_font)
    draw.text((width // 2, 1260), "Text to Voice to Video", anchor="mm", fill=(120, 135, 160), font=small_font)

    _draw_waveform(draw, width, 1400)
    _draw_subtitle(draw, subtitle_text, width, 1550)
    canvas.convert("RGB").save(output_path)


def _paste_avatar_image(canvas: Image.Image, avatar_bytes: bytes, avatar_box: tuple[int, int, int, int]) -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
        file.write(avatar_bytes)
        image_path = Path(file.name)
    try:
        avatar = Image.open(image_path).convert("RGBA")
    finally:
        image_path.unlink(missing_ok=True)

    box_width = avatar_box[2] - avatar_box[0]
    box_height = avatar_box[3] - avatar_box[1]
    avatar.thumbnail((box_width, box_height))
    x = avatar_box[0] + (box_width - avatar.width) // 2
    y = avatar_box[1] + (box_height - avatar.height) // 2
    mask = Image.new("L", (box_width, box_height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, box_width, box_height), fill=255)
    layer = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
    layer.paste(avatar, (x - avatar_box[0], y - avatar_box[1]), avatar)
    alpha = layer.getchannel("A")
    layer.putalpha(ImageChops.multiply(alpha, mask))
    canvas.alpha_composite(layer, (avatar_box[0], avatar_box[1]))


def _draw_waveform(draw: ImageDraw.ImageDraw, width: int, y: int) -> None:
    center = width // 2
    bar_count = 38
    gap = 10
    bar_width = 10
    total = bar_count * bar_width + (bar_count - 1) * gap
    start_x = center - total // 2
    for index in range(bar_count):
        wave = 0.45 + 0.55 * abs(math.sin(index * 0.72))
        bar_height = int(34 + wave * 118)
        x = start_x + index * (bar_width + gap)
        color = (49, 215, 255) if index % 3 else (183, 248, 113)
        draw.rounded_rectangle((x, y - bar_height // 2, x + bar_width, y + bar_height // 2), radius=5, fill=color)


def _draw_subtitle(draw: ImageDraw.ImageDraw, text: str, width: int, y: int) -> None:
    clean = " ".join(text.replace("\n", " ").split()).strip() or "你好，我是凯强 AI 数字人"
    lines = [clean[i : i + 16] for i in range(0, min(len(clean), 48), 16)] or [clean]
    font = _font(46)
    line_height = 68
    box_height = line_height * len(lines) + 48
    box = (90, y - 24, width - 90, y + box_height)
    draw.rounded_rectangle(box, radius=28, fill=(0, 0, 0), outline=(49, 215, 255), width=2)
    for index, line in enumerate(lines):
        draw.text((width // 2, y + 24 + index * line_height), line, anchor="mm", fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))


def _build_subtitle_overlay(output_path: Path, text: str) -> None:
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    _draw_subtitle(draw, text, 1080, 1550)
    canvas.save(output_path)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()
