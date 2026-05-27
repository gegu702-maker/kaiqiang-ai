from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from supabase import Client

from app.core.config import settings
from app.services.storage import upload_public_bytes


async def render_static_avatar_video(
    supabase: Client,
    *,
    audio_url: str,
    subtitle_text: str,
    duration: float | None = None,
) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        audio_response = await client.get(audio_url)
        audio_response.raise_for_status()
        audio_bytes = audio_response.content

    video_seconds = max(1.0, float(duration or 0) or _probe_duration_from_bytes(audio_bytes))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        background_path = tmp_path / "avatar.png"
        audio_path = tmp_path / "voice.mp3"
        subtitle_path = tmp_path / "subtitles.srt"
        output_path = tmp_path / "static-avatar.mp4"

        _build_avatar_background(background_path)
        audio_path.write_bytes(audio_bytes)
        subtitle_path.write_text(_build_srt(subtitle_text, video_seconds), encoding="utf-8")

        cmd = [
            settings.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
            "-vf",
            f"subtitles={_ffmpeg_path(subtitle_path)}:force_style='FontName=Arial,Fontsize=42,PrimaryColour=&HFFFFFF,OutlineColour=&H111111,BorderStyle=1,Outline=2,Alignment=2,MarginV=210'",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
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
            raise HTTPException(status_code=500, detail=f"FFmpeg static avatar render failed: {result.stderr[-1200:]}")

        video_bytes = output_path.read_bytes()

    return upload_public_bytes(
        supabase,
        settings.supabase_video_bucket,
        video_bytes,
        "debug/static-avatar",
        ".mp4",
        "video/mp4",
    )


def _build_avatar_background(output_path: Path) -> None:
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
    canvas.convert("RGB").save(output_path)


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


def _build_srt(text: str, duration: float) -> str:
    clean = " ".join(text.replace("\n", " ").split()).strip() or "你好，我是凯强 AI 数字人"
    chunks = [clean[i : i + 18] for i in range(0, len(clean), 18)]
    total_ms = max(1200, int(duration * 1000))
    per_ms = max(1200, total_ms // max(len(chunks), 1))
    lines: list[str] = []
    start = 0
    for index, chunk in enumerate(chunks, start=1):
        end = min(total_ms, start + per_ms)
        if end <= start:
            break
        lines.append(f"{index}\n{_ts(start)} --> {_ts(end)}\n{chunk}\n")
        start = end
        if start >= total_ms:
            break
    return "\n".join(lines)


def _ts(ms: int) -> str:
    seconds, milli = divmod(ms, 1000)
    minutes, second = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{second:02d},{milli:03d}"


def _probe_duration_from_bytes(audio_bytes: bytes) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "voice.mp3"
        audio_path.write_bytes(audio_bytes)
        candidate = settings.ffmpeg_path.replace("ffmpeg", "ffprobe")
        result = subprocess.run(
            [
                candidate,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        return 5.0
    try:
        return max(1.0, float(result.stdout.strip()))
    except ValueError:
        return 5.0


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


def _ffmpeg_path(path: Path) -> str:
    value = path.as_posix().replace(":", "\\:").replace("'", "\\'")
    return f"'{value}'"
