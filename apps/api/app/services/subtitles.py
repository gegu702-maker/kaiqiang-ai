from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    lines: list[str]


class SubtitleBurnError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class MediaDurationError(RuntimeError):
    def __init__(self, detail: dict) -> None:
        super().__init__(str(detail.get("message") or "Media duration validation failed"))
        self.detail = detail


@dataclass(frozen=True)
class MediaInfo:
    video_duration: float
    audio_duration: float | None
    fps: float
    video_frames: int | None

    @property
    def frame_duration(self) -> float:
        return 1.0 / self.fps if self.fps > 0 else 0.0


PUNCTUATION_PATTERN = re.compile(r"([^。！？!?；;，,.\n]+[。！？!?；;，,.]?)")


def normalize_script_text(text: str | None) -> str:
    return " ".join((text or "").replace("\r", "\n").split()).strip()


def build_script_webvtt(script: str) -> bytes:
    chunks = _split_webvtt_script(script)
    lines = ["WEBVTT", ""]
    for index, chunk in enumerate(chunks or [" "]):
        start_seconds = index * 4
        end_seconds = start_seconds + 4
        lines.extend(
            [
                f"{_format_vtt_timestamp(start_seconds)} --> {_format_vtt_timestamp(end_seconds)}",
                chunk,
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


def split_subtitle_text(text: str, *, max_line_chars: int = 16, max_lines: int = 2) -> list[list[str]]:
    clean = normalize_script_text(text)
    if not clean:
        return []

    chunks: list[str] = []
    for match in PUNCTUATION_PATTERN.finditer(clean):
        chunk = match.group(0).strip()
        if chunk:
            chunks.extend(_wrap_text(chunk, max_line_chars))
    if not chunks:
        chunks = _wrap_text(clean, max_line_chars)

    cues: list[list[str]] = []
    current: list[str] = []
    for chunk in chunks:
        if len(current) >= max_lines:
            cues.append(current)
            current = []
        current.append(chunk)
    if current:
        cues.append(current)
    return cues


def build_subtitle_segments(text: str, duration_seconds: float) -> list[SubtitleSegment]:
    cues = split_subtitle_text(text)
    if not cues:
        return []

    total_duration = max(float(duration_seconds or 0), len(cues) * 1.2)
    weights = [max(1, sum(_display_len(line) for line in cue)) for cue in cues]
    total_weight = sum(weights) or len(cues)
    raw_durations = [total_duration * weight / total_weight for weight in weights]
    cue_durations = [min(4.5, max(1.2, value)) for value in raw_durations]

    scale = total_duration / sum(cue_durations)
    if scale < 1:
        cue_durations = [max(1.0, value * scale) for value in cue_durations]

    segments: list[SubtitleSegment] = []
    cursor = 0.0
    for cue, cue_duration in zip(cues, cue_durations):
        end = min(total_duration, cursor + cue_duration)
        if end - cursor < 0.5:
            end = min(total_duration, cursor + 0.5)
        segments.append(SubtitleSegment(start=cursor, end=end, lines=cue))
        cursor = end
        if cursor >= total_duration:
            break
    if segments:
        last = segments[-1]
        segments[-1] = SubtitleSegment(start=last.start, end=total_duration, lines=last.lines)
    return segments


def write_ass_file(
    segments: list[SubtitleSegment],
    output_path: Path,
    *,
    video_width: int = 1080,
    video_height: int = 1920,
    font_name: str | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_size = max(34, min(62, round(video_height * 0.031)))
    outline = max(2, round(font_size * 0.08))
    margin_v = max(150, round(video_height * 0.12))
    style_font = (font_name or settings.avatar_subtitle_font or "Noto Sans CJK SC").strip()
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        (
            f"Style: Default,{style_font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,"
            f"&H80000000,-1,0,0,0,100,100,0,0,1,{outline},1,2,90,90,{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for segment in segments:
        text = r"\N".join(_escape_ass_text(line) for line in segment.lines[:2])
        lines.append(
            f"Dialogue: 0,{_format_ass_time(segment.start)},{_format_ass_time(segment.end)},"
            f"Default,,0,0,0,,{text}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def burn_subtitles_to_video(input_mp4: Path, ass_path: Path, output_mp4: Path, ffmpeg_path: str | None = None) -> None:
    ffmpeg = ffmpeg_path or settings.ffmpeg_path
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    input_media = probe_media_info(input_mp4, ffmpeg)
    validate_stream_duration_alignment(input_media, stage="subtitle_input")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_mp4),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        f"ass={ass_path.name}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-threads",
        "1",
        "-x264-params",
        "rc-lookahead=0:sync-lookahead=0:ref=1:no-mbtree=1",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(ass_path.parent),
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    if result.returncode != 0:
        raise SubtitleBurnError(
            "FFmpeg subtitle burn failed",
            _build_burn_diagnostics(
                cmd=cmd,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                input_mp4=input_mp4,
                ass_path=ass_path,
                output_mp4=output_mp4,
                ffmpeg_path=ffmpeg,
            ),
        )
    if not output_mp4.exists() or output_mp4.stat().st_size < 1024:
        raise SubtitleBurnError(
            "FFmpeg subtitle burn produced an empty output",
            _build_burn_diagnostics(
                cmd=cmd,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                input_mp4=input_mp4,
                ass_path=ass_path,
                output_mp4=output_mp4,
                ffmpeg_path=ffmpeg,
            ),
        )
    output_media = probe_media_info(output_mp4, ffmpeg)
    try:
        validate_stream_duration_alignment(output_media, stage="subtitle_output")
        _validate_audio_preserved(input_media, output_media)
    except MediaDurationError:
        output_mp4.unlink(missing_ok=True)
        raise


def probe_video_duration(input_mp4: Path, ffmpeg_path: str | None = None) -> float:
    return round(probe_media_info(input_mp4, ffmpeg_path).video_duration, 2)


def probe_media_info(input_mp4: Path, ffmpeg_path: str | None = None) -> MediaInfo:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        candidate = (ffmpeg_path or settings.ffmpeg_path).replace("ffmpeg", "ffprobe")
        ffprobe = candidate if Path(candidate).exists() else "ffprobe"
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration,r_frame_rate,avg_frame_rate,nb_frames",
            "-of",
            "json",
            str(input_mp4),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Unable to probe video duration")
    try:
        data = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail="Unable to probe video duration") from error
    format_duration = _safe_positive_float((data.get("format") or {}).get("duration"))
    video_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if not video_stream:
        raise HTTPException(status_code=500, detail="Video stream missing")
    video_duration = _safe_positive_float(video_stream.get("duration")) or format_duration
    audio_duration = _safe_positive_float(audio_stream.get("duration")) if audio_stream else None
    if audio_stream and not audio_duration:
        audio_duration = format_duration
    fps = _parse_rate(video_stream.get("avg_frame_rate")) or _parse_rate(video_stream.get("r_frame_rate"))
    if not video_duration or not fps:
        raise HTTPException(status_code=500, detail="Invalid video duration")
    return MediaInfo(
        video_duration=video_duration,
        audio_duration=audio_duration,
        fps=fps,
        video_frames=_safe_optional_int(video_stream.get("nb_frames")),
    )


def validate_stream_duration_alignment(media: MediaInfo, *, stage: str) -> None:
    if media.audio_duration is None:
        return
    shortfall = media.audio_duration - media.video_duration
    if shortfall > media.frame_duration + 0.001:
        raise MediaDurationError(
            {
                "code": "avatar_video_shorter_than_audio",
                "message": "Video stream is too short to preserve the complete audio track.",
                "stage": stage,
                "video_duration": round(media.video_duration, 6),
                "audio_duration": round(media.audio_duration, 6),
                "fps": round(media.fps, 6),
                "video_frames": media.video_frames,
                "max_shortfall": round(media.frame_duration, 6),
                "actual_shortfall": round(shortfall, 6),
            }
        )
    if stage == "subtitle_output" and -shortfall > media.frame_duration + 0.001:
        raise MediaDurationError(
            {
                "code": "avatar_final_stream_duration_mismatch",
                "message": "Final video and audio stream durations differ by more than one frame.",
                "stage": stage,
                "video_duration": round(media.video_duration, 6),
                "audio_duration": round(media.audio_duration, 6),
                "fps": round(media.fps, 6),
                "video_frames": media.video_frames,
                "max_difference": round(media.frame_duration, 6),
                "actual_difference": round(abs(shortfall), 6),
            }
        )


def _validate_audio_preserved(input_media: MediaInfo, output_media: MediaInfo) -> None:
    if input_media.audio_duration is None or output_media.audio_duration is None:
        return
    lost_audio = input_media.audio_duration - output_media.audio_duration
    tolerance = max(input_media.frame_duration, output_media.frame_duration) + 0.001
    if lost_audio > tolerance:
        raise MediaDurationError(
            {
                "code": "avatar_audio_truncated_during_subtitle_burn",
                "message": "Subtitle rendering shortened the audio track.",
                "stage": "subtitle_output",
                "input_audio_duration": round(input_media.audio_duration, 6),
                "output_audio_duration": round(output_media.audio_duration, 6),
                "lost_audio_duration": round(lost_audio, 6),
                "max_allowed_loss": round(tolerance, 6),
            }
        )


def _parse_rate(value: object) -> float:
    try:
        numerator, denominator = str(value or "0/0").split("/", 1)
        parsed = float(numerator) / float(denominator)
        return parsed if math.isfinite(parsed) and parsed > 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _safe_positive_float(value: object) -> float:
    try:
        parsed = float(value or 0)
        return parsed if math.isfinite(parsed) and parsed > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_int(value: object) -> int | None:
    try:
        return int(value) if value not in {None, "", "N/A"} else None
    except (TypeError, ValueError):
        return None


def _wrap_text(text: str, max_line_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        if _display_len(current + char) > max_line_chars and current:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def _build_burn_diagnostics(
    *,
    cmd: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
    input_mp4: Path,
    ass_path: Path,
    output_mp4: Path,
    ffmpeg_path: str,
) -> dict:
    return {
        "returncode": returncode,
        "command": cmd,
        "stderr_tail": stderr[-3000:],
        "stdout_tail": stdout[-1000:],
        "input_mp4_path": str(input_mp4),
        "input_mp4_exists": input_mp4.exists(),
        "input_mp4_size": _file_size(input_mp4),
        "ass_path": str(ass_path),
        "ass_exists": ass_path.exists(),
        "ass_size": _file_size(ass_path),
        "output_mp4_path": str(output_mp4),
        "output_mp4_exists": output_mp4.exists(),
        "output_mp4_size": _file_size(output_mp4),
        "ffmpeg_path": ffmpeg_path,
        "selected_subtitle_font": settings.avatar_subtitle_font,
        "cwd": str(ass_path.parent),
    }


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.exists() else None
    except OSError:
        return None


def _split_webvtt_script(script: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", script.strip())
    if not normalized:
        return [" "]

    sentences = [part.strip() for part in re.split(r"(?<=[。！？.!?])\s*", normalized) if part.strip()]
    chunks: list[str] = []
    for sentence in sentences:
        while len(sentence) > 42:
            chunks.append(sentence[:42])
            sentence = sentence[42:]
        if sentence:
            chunks.append(sentence)
    return chunks or [normalized[:42]]


def _display_len(text: str) -> float:
    return sum(0.5 if ord(char) < 128 else 1 for char in text)


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _format_ass_time(seconds: float) -> str:
    seconds = max(0, seconds)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    whole_total_seconds = int(seconds)
    if centiseconds >= 100:
        whole_total_seconds += 1
        centiseconds = 0
    hours = whole_total_seconds // 3600
    minutes = (whole_total_seconds % 3600) // 60
    whole_seconds = whole_total_seconds % 60
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _format_vtt_timestamp(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.000"
