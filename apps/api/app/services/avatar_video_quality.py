from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".webm"}
SUPPORTED_FORMAT_TOKENS = {"mp4", "mov", "quicktime", "webm", "matroska"}

MIN_DURATION_SECONDS = 8.0
RECOMMENDED_MIN_DURATION_SECONDS = 10.0
RECOMMENDED_MAX_DURATION_SECONDS = 30.0
MAX_DURATION_SECONDS = 60.0
MIN_SHORT_SIDE = 540
MIN_LONG_SIDE = 720
MIN_FPS = 20.0
MAX_FPS = 60.0


@dataclass(frozen=True)
class VideoQualityReason:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class VideoQualityMetrics:
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    format: str | None = None


@dataclass(frozen=True)
class VideoQualityResult:
    success: bool
    grade: str
    reasons: list[VideoQualityReason]
    metrics: VideoQualityMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "grade": self.grade,
            "reasons": [reason.__dict__ for reason in self.reasons],
            "metrics": self.metrics.__dict__,
        }


def check_avatar_video_quality(video_path: str | Path) -> dict[str, Any]:
    path = Path(video_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return _build_result(
            success=True,
            metrics=VideoQualityMetrics(format=path.suffix.lower().lstrip(".") or None),
            reasons=[
                VideoQualityReason(
                    code="unsupported_format",
                    severity="blocking",
                    message="当前视频格式暂不支持，请上传 MP4、MOV 或 WebM。",
                )
            ],
        ).to_dict()

    try:
        metadata = _probe_video(path)
    except Exception as error:
        return VideoQualityResult(
            success=False,
            grade="C",
            reasons=[
                VideoQualityReason(
                    code="probe_failed",
                    severity="blocking",
                    message="视频读取失败，请重新上传。",
                )
            ],
            metrics=VideoQualityMetrics(format=path.suffix.lower().lstrip(".") or None),
        ).to_dict()

    return evaluate_video_quality_metadata(metadata, file_extension=path.suffix).to_dict()


def evaluate_video_quality_metadata(metadata: VideoQualityMetrics, file_extension: str = "") -> VideoQualityResult:
    reasons: list[VideoQualityReason] = []
    format_tokens = {token.strip().lower() for token in (metadata.format or "").replace("/", ",").split(",") if token.strip()}
    extension = file_extension.lower()

    if extension and extension not in SUPPORTED_EXTENSIONS:
        reasons.append(VideoQualityReason("unsupported_format", "blocking", "当前视频格式暂不支持，请上传 MP4、MOV 或 WebM。"))
    elif metadata.format and not (format_tokens & SUPPORTED_FORMAT_TOKENS):
        reasons.append(VideoQualityReason("unsupported_format", "blocking", "当前视频格式暂不支持，请上传 MP4、MOV 或 WebM。"))

    if not metadata.width or not metadata.height or not metadata.codec:
        reasons.append(VideoQualityReason("invalid_video_stream", "blocking", "没有检测到可用的视频画面。"))

    if metadata.duration_seconds is None or metadata.duration_seconds <= 0:
        reasons.append(VideoQualityReason("probe_failed", "blocking", "视频时长读取失败，请重新上传。"))
    elif metadata.duration_seconds < MIN_DURATION_SECONDS:
        reasons.append(VideoQualityReason("video_too_short", "blocking", "视频太短，建议至少 8-10 秒。"))
    elif metadata.duration_seconds > MAX_DURATION_SECONDS:
        reasons.append(VideoQualityReason("video_too_long", "blocking", "视频较长，建议控制在 60 秒以内。"))
    elif metadata.duration_seconds < RECOMMENDED_MIN_DURATION_SECONDS or metadata.duration_seconds > RECOMMENDED_MAX_DURATION_SECONDS:
        reasons.append(VideoQualityReason("duration_suboptimal", "warning", "可以生成，但 10-30 秒的视频更稳定。"))

    if metadata.width and metadata.height:
        short_side = min(metadata.width, metadata.height)
        long_side = max(metadata.width, metadata.height)
        if short_side < MIN_SHORT_SIDE or long_side < MIN_LONG_SIDE:
            reasons.append(VideoQualityReason("low_resolution", "blocking", "视频分辨率偏低，建议使用 720p 或更清晰的视频。"))

    if metadata.fps is not None and metadata.fps > 0 and (metadata.fps < MIN_FPS or metadata.fps > MAX_FPS):
        reasons.append(VideoQualityReason("fps_unusual", "warning", "视频帧率不常见，可能影响生成稳定性。"))

    return _build_result(success=True, metrics=metadata, reasons=reasons)


def _build_result(success: bool, metrics: VideoQualityMetrics, reasons: list[VideoQualityReason]) -> VideoQualityResult:
    has_blocking = any(reason.severity == "blocking" for reason in reasons)
    has_warning = any(reason.severity == "warning" for reason in reasons)
    grade = "C" if has_blocking else "B" if has_warning else "A"
    return VideoQualityResult(success=success, grade=grade, reasons=reasons, metrics=metrics)


def _probe_video(video_path: Path) -> VideoQualityMetrics:
    command = [
        _ffprobe_path(),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,r_frame_rate:format=duration,format_name",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=20)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffprobe failed").strip())

    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        return VideoQualityMetrics(format=(payload.get("format") or {}).get("format_name"))

    stream = streams[0]
    format_info = payload.get("format") or {}
    return VideoQualityMetrics(
        duration_seconds=_parse_float(format_info.get("duration")),
        width=_parse_int(stream.get("width")),
        height=_parse_int(stream.get("height")),
        fps=_parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
        codec=stream.get("codec_name"),
        format=format_info.get("format_name"),
    )


def _ffprobe_path() -> str:
    ffmpeg_path = settings.ffmpeg_path or "ffmpeg"
    path = Path(ffmpeg_path)
    if path.name.lower() in {"ffmpeg", "ffmpeg.exe"}:
        probe_name = "ffprobe.exe" if path.name.lower().endswith(".exe") else "ffprobe"
        return str(path.with_name(probe_name))
    return "ffprobe"


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_fps(value: Any) -> float | None:
    if not value:
        return None
    text = str(value)
    try:
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        return float(text)
    except (TypeError, ValueError):
        return None
