from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.config import settings

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\u3130-\u318f\uac00-\ud7af]")
PRIMARY_BREAK_RE = re.compile(r"([。！？!?；;]+)")
SECONDARY_BREAK_RE = re.compile(r"([，,、]+)")


def burn_subtitles_into_video_bytes(video_bytes: bytes, subtitle_text: str) -> bytes:
    clean_text = " ".join((subtitle_text or "").replace("\n", " ").split()).strip()
    if not clean_text:
        return video_bytes

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.mp4"
            subtitle_path = tmp_path / "subtitles.ass"
            output_path = tmp_path / "output.mp4"

            input_path.write_bytes(video_bytes)
            metadata = _probe_video(input_path)
            duration = max(0.1, _safe_float(metadata.get("duration")))
            width = max(1, int(metadata.get("width") or 1080))
            height = max(1, int(metadata.get("height") or 1920))

            subtitle_path.write_text(_build_ass(clean_text, duration, width, height), encoding="utf-8-sig")
            cmd = [
                settings.ffmpeg_path,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"subtitles={_ffmpeg_filter_path(subtitle_path)}",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-1600:] or "ffmpeg exited with non-zero status")
            output_bytes = output_path.read_bytes()
            if len(output_bytes) < 1024 or b"ftyp" not in output_bytes[:32]:
                raise RuntimeError("ffmpeg output is not a valid MP4 file")
            return output_bytes
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"subtitle burn failed: {error}") from error


def _probe_video(path: Path) -> dict[str, Any]:
    cmd = [
        _ffprobe_path(),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or "ffprobe failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError(f"ffprobe returned invalid JSON: {error}") from error
    stream = (payload.get("streams") or [{}])[0]
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration": (payload.get("format") or {}).get("duration") or stream.get("duration"),
    }


def _build_ass(text: str, duration: float, width: int, height: int) -> str:
    font_size = _font_size(height)
    margin_v = max(60, int(height * 0.115))
    outline = max(2, int(font_size * 0.075))
    cues = _build_cues(text, duration)
    events = "\n".join(
        f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{_escape_ass_text(lines)}"
        for start, end, lines in cues
    )
    return f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{_font_name()},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H66000000,0,0,0,0,100,100,0,0,1,{outline},0,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{events}
"""


def _build_cues(text: str, duration: float) -> list[tuple[float, float, list[str]]]:
    segments = _split_segments(text)
    max_segments = max(1, int(math.ceil(duration / 1.8)))
    if len(segments) > max_segments:
        segments = _merge_segments(segments, max_segments)
    segment_count = max(1, len(segments))
    per_segment = duration / segment_count
    if duration >= 1.8:
        per_segment = min(4.2, max(1.8, per_segment))

    cues: list[tuple[float, float, list[str]]] = []
    start = 0.0
    for index, lines in enumerate(segments):
        if index == segment_count - 1:
            end = max(start + 0.1, duration)
        else:
            end = min(duration, start + per_segment)
        cues.append((start, end, lines))
        start = end
        if start >= duration:
            break
    return cues or [(0.0, max(0.1, duration), [_trim_text(text, 42)])]


def _split_segments(text: str) -> list[list[str]]:
    cjk = _is_cjk_heavy(text)
    line_limit = 16 if cjk else 38
    sentences = _split_sentences(text)
    segments: list[list[str]] = []
    for sentence in sentences:
        lines = _wrap_cjk(sentence, line_limit) if cjk else _wrap_words(sentence, line_limit)
        for index in range(0, len(lines), 2):
            segments.append(lines[index : index + 2])
    return [segment for segment in segments if segment]


def _split_sentences(text: str) -> list[str]:
    primary = _split_keep_delimiter(text, PRIMARY_BREAK_RE)
    sentences: list[str] = []
    for item in primary:
        if len(item) > 44:
            sentences.extend(_split_keep_delimiter(item, SECONDARY_BREAK_RE))
        else:
            sentences.append(item)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _split_keep_delimiter(text: str, pattern: re.Pattern[str]) -> list[str]:
    parts = pattern.split(text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        current += part
        if pattern.fullmatch(part):
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def _wrap_cjk(text: str, limit: int) -> list[str]:
    clean = text.strip()
    return [_trim_text(clean[index : index + limit], limit) for index in range(0, len(clean), limit)] or [clean]


def _wrap_words(text: str, limit: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [_trim_text(text, limit)]


def _merge_segments(segments: list[list[str]], target_count: int) -> list[list[str]]:
    merged = segments[:]
    while len(merged) > target_count and len(merged) > 1:
        left = merged.pop(0)
        right = merged.pop(0)
        merged.insert(0, (left + right)[:2])
    return merged


def _is_cjk_heavy(text: str) -> bool:
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return False
    cjk_count = sum(1 for char in non_space if CJK_RE.match(char))
    return cjk_count / len(non_space) >= 0.35


def _font_size(height: int) -> int:
    return max(34, min(64, round(height * 0.029)))


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _font_name() -> str:
    return "Noto Sans CJK SC"


def _ass_time(seconds: float) -> str:
    total_centiseconds = max(0, int(round(seconds * 100)))
    centiseconds = total_centiseconds % 100
    total_seconds = total_centiseconds // 100
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours}:{mins:02d}:{secs:02d}.{centiseconds:02d}"


def _escape_ass_text(lines: list[str]) -> str:
    return r"\N".join(_escape_ass_line(line) for line in lines[:2])


def _escape_ass_line(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", "｛").replace("}", "｝").strip()


def _trim_text(text: str, limit: int) -> str:
    return text.strip()[:limit]


def _ffmpeg_filter_path(path: Path) -> str:
    value = path.as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"'{value}'"


def _ffprobe_path() -> str:
    ffmpeg = Path(settings.ffmpeg_path)
    if ffmpeg.name.lower() in {"ffmpeg", "ffmpeg.exe"}:
        suffix = ".exe" if ffmpeg.suffix.lower() == ".exe" else ""
        return str(ffmpeg.with_name(f"ffprobe{suffix}"))
    return settings.ffmpeg_path.replace("ffmpeg", "ffprobe")
