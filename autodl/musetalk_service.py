from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(os.getenv("MUSETALK_ROOT", "/root/MuseTalk"))
OUTPUT_ROOT = Path(os.getenv("MUSETALK_OUTPUT_ROOT", "/root/autodl-tmp/results"))
INPUT_ROOT = Path(os.getenv("MUSETALK_INPUT_ROOT", "/root/autodl-tmp/avatar_inputs"))
API_KEY = os.getenv("MUSETALK_API_KEY", "")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
AUDIO_SAMPLE_RATE = 16000
AUDIO_TAIL_PADDING_SECONDS = 0.4
FPS_INTEGER_TOLERANCE = 0.01

logger = logging.getLogger(__name__)

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
INPUT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Kaiqiang MuseTalk GPU Service")
app.mount("/results", StaticFiles(directory=str(OUTPUT_ROOT)), name="results")
gpu_lock = asyncio.Lock()


class GenerateRequest(BaseModel):
    video_url: str | None = None
    audio_url: str | None = None
    video_path: str | None = None
    audio_path: str | None = None
    task_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "engine": "musetalk",
        "root": str(ROOT),
    }


@app.post("/generate")
async def generate(payload: GenerateRequest, request: Request, authorization: str | None = Header(default=None)) -> dict:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid MuseTalk API key")
    if not ROOT.exists():
        raise HTTPException(status_code=500, detail=f"MuseTalk root missing: {ROOT}")

    task_id = _safe_task_id(payload.task_id)
    work_dir = INPUT_ROOT / task_id
    work_dir.mkdir(parents=True, exist_ok=True)
    original_video_path = work_dir / "original_video"
    original_audio_path = work_dir / "original_audio"
    video_path = work_dir / "musetalk_input.mp4"
    audio_path = work_dir / "musetalk_input.wav"
    config_path = ROOT / "configs" / "inference" / "generated" / f"{task_id}.yaml"
    result_dir = ROOT / "results" / "api" / task_id

    await _prepare_input(payload.video_url, payload.video_path, original_video_path, "video")
    await _prepare_input(payload.audio_url, payload.audio_path, original_audio_path, "audio")

    input_video = _probe_media(original_video_path)
    input_audio = _probe_media(original_audio_path)
    target_fps = _select_cfr_fps(input_video)
    _prepare_cfr_video(original_video_path, video_path, input_video, target_fps)
    normalized_video = _probe_media(video_path)
    tail_padding_seconds = _calculate_working_audio_padding(
        original_duration=float(input_audio["audio_duration"]),
        target_fps=target_fps,
    )
    _prepare_working_audio(
        original_audio_path,
        audio_path,
        tail_padding_seconds=tail_padding_seconds,
    )
    working_audio = _probe_media(audio_path)
    _validate_prepared_inputs(
        input_audio=input_audio,
        working_audio=working_audio,
        normalized_video=normalized_video,
        target_fps=target_fps,
    )
    logger.info(
        "MuseTalk media prepared task_id=%s input_video_fps=%.6f input_video_duration=%.6f "
        "normalized_video_fps=%.6f normalized_video_duration=%.6f original_audio_duration=%.6f "
        "working_audio_duration=%.6f tail_padding_seconds=%.6f target_fps=%s",
        task_id,
        input_video["fps"],
        input_video["video_duration"],
        normalized_video["fps"],
        normalized_video["video_duration"],
        input_audio["audio_duration"],
        working_audio["audio_duration"],
        tail_padding_seconds,
        target_fps,
    )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {"task_0": {"video_path": str(video_path), "audio_path": str(audio_path)}},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    async with gpu_lock:
        completed = await asyncio.to_thread(_run_inference, config_path, result_dir)

    output_media = _probe_media(completed)
    required_duration = input_audio["audio_duration"] + AUDIO_TAIL_PADDING_SECONDS
    _validate_musetalk_output(output_media, required_duration=required_duration)
    logger.info(
        "MuseTalk media output task_id=%s video_duration=%.6f video_frames=%s video_fps=%.6f "
        "audio_duration=%.6f required_duration=%.6f",
        task_id,
        output_media["video_duration"],
        output_media["video_frames"],
        output_media["fps"],
        output_media["audio_duration"],
        required_duration,
    )

    output_path = OUTPUT_ROOT / f"{task_id}.mp4"
    shutil.copy2(completed, output_path)
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "completed",
        "task_id": task_id,
        "video_url": f"{base_url}/results/{output_path.name}",
    }


async def _download(url: str, path: Path) -> None:
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        response = await client.get(url)
    if not response.is_success:
        raise HTTPException(status_code=400, detail=f"Input download failed: {response.status_code}")
    path.write_bytes(response.content)


async def _prepare_input(url: str | None, local_path: str | None, destination: Path, label: str) -> None:
    if local_path:
        _copy_local_data_file(local_path, destination, label)
        return
    if url:
        await _download(url, destination)
        return
    raise HTTPException(status_code=400, detail=f"{label}_url or {label}_path is required")


def _copy_local_data_file(raw_path: str, destination: Path, label: str) -> None:
    source = Path(raw_path).expanduser().resolve()
    allowed_root = (ROOT / "data").resolve()
    if allowed_root not in source.parents:
        raise HTTPException(status_code=400, detail=f"{label}_path must be under {allowed_root}")
    if not source.is_file():
        raise HTTPException(status_code=400, detail=f"{label}_path missing: {source}")
    shutil.copy2(source, destination)


def _run_inference(config_path: Path, result_dir: Path) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "/root/miniconda3/envs/musetalk/bin/python",
        "-m",
        "scripts.inference",
        "--inference_config",
        str(config_path),
        "--result_dir",
        str(result_dir),
        "--unet_model_path",
        "./models/musetalkV15/unet.pth",
        "--unet_config",
        "./models/musetalkV15/musetalk.json",
        "--version",
        "v15",
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"MuseTalk inference failed: {result.stderr[-2000:] or result.stdout[-2000:]}",
        )
    outputs = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    outputs = [item for item in outputs if not item.name.startswith("temp_")]
    if not outputs:
        raise HTTPException(status_code=500, detail="MuseTalk output video missing")
    return outputs[0]


def _select_cfr_fps(media: dict[str, float | int]) -> int:
    fps = float(media.get("fps") or 0)
    if not math.isfinite(fps) or fps <= 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_video_fps", "message": "Unable to determine a valid input video frame rate."},
        )
    return max(1, round(fps))


def _prepare_cfr_video(
    source: Path,
    destination: Path,
    media: dict[str, float | int],
    target_fps: int,
) -> None:
    fps = float(media["fps"])
    is_cfr = bool(media.get("is_cfr"))
    if is_cfr and abs(fps - target_fps) <= FPS_INTEGER_TOLERANCE:
        shutil.copy2(source, destination)
        return

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        f"fps={target_fps}",
        "-fps_mode",
        "cfr",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(destination),
    ]
    _run_ffmpeg(cmd, "video CFR normalization")


def _prepare_working_audio(
    source: Path,
    destination: Path,
    *,
    tail_padding_seconds: float,
) -> None:
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source),
        "-af",
        f"apad=pad_dur={tail_padding_seconds:.9f}",
        "-ac",
        "1",
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    _run_ffmpeg(cmd, "audio preparation")


def _calculate_working_audio_padding(*, original_duration: float, target_fps: int) -> float:
    required_duration = original_duration + AUDIO_TAIL_PADDING_SECONDS
    covering_frame_count = math.ceil(required_duration * target_fps)
    frame_aligned_duration = covering_frame_count / target_fps
    one_sample_guard = 1.0 / AUDIO_SAMPLE_RATE
    return max(AUDIO_TAIL_PADDING_SECONDS, frame_aligned_duration - original_duration) + one_sample_guard


def _validate_prepared_inputs(
    *,
    input_audio: dict[str, float | int],
    working_audio: dict[str, float | int],
    normalized_video: dict[str, float | int],
    target_fps: int,
) -> None:
    normalized_fps = float(normalized_video["fps"])
    if not bool(normalized_video.get("is_cfr")) or abs(normalized_fps - target_fps) > FPS_INTEGER_TOLERANCE:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "video_cfr_normalization_failed",
                "message": "Prepared MuseTalk video is not at the requested constant frame rate.",
                "target_fps": target_fps,
                "actual_fps": round(normalized_fps, 6),
            },
        )

    required_audio_duration = float(input_audio["audio_duration"]) + AUDIO_TAIL_PADDING_SECONDS
    if float(working_audio["audio_duration"]) + 0.005 < required_audio_duration:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "audio_tail_padding_failed",
                "message": "Prepared MuseTalk audio does not preserve the source plus the required tail padding.",
                "required_duration": round(required_audio_duration, 6),
                "actual_duration": round(float(working_audio["audio_duration"]), 6),
            },
        )


def _validate_musetalk_output(media: dict[str, float | int], *, required_duration: float) -> None:
    video_duration = float(media.get("video_duration") or 0)
    if video_duration + 0.001 < required_duration:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "musetalk_output_duration_shortfall",
                "message": "MuseTalk output video does not cover the complete source audio and tail padding.",
                "video_duration": round(video_duration, 6),
                "required_duration": round(required_duration, 6),
                "video_frames": media.get("video_frames"),
                "fps": round(float(media.get("fps") or 0), 6),
            },
        )


def _probe_media(path: Path) -> dict[str, float | int]:
    result = subprocess.run(
        [
            FFPROBE_PATH,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration,r_frame_rate,avg_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail={"code": "media_probe_failed", "message": result.stderr[-500:]})
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "media_probe_failed", "message": "Invalid ffprobe output."},
        ) from error

    format_duration = _safe_float((data.get("format") or {}).get("duration"))
    video_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), {})
    average_fps = _parse_rate(video_stream.get("avg_frame_rate"))
    nominal_fps = _parse_rate(video_stream.get("r_frame_rate"))
    fps = average_fps or nominal_fps
    return {
        "video_duration": _safe_float(video_stream.get("duration")) or (format_duration if video_stream else 0),
        "audio_duration": _safe_float(audio_stream.get("duration")) or (format_duration if audio_stream else 0),
        "fps": fps,
        "video_frames": _safe_int(video_stream.get("nb_frames")),
        "is_cfr": bool(fps and nominal_fps and abs(fps - nominal_fps) <= 0.001),
    }


def _run_ffmpeg(cmd: list[str], label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    output_path = Path(cmd[-1])
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
        raise HTTPException(
            status_code=500,
            detail={
                "code": f"{label.replace(' ', '_')}_failed",
                "message": f"FFmpeg {label} failed.",
                "stderr": result.stderr[-1000:],
            },
        )


def _parse_rate(value: object) -> float:
    raw = str(value or "0/0")
    try:
        numerator, denominator = raw.split("/", 1)
        parsed = float(numerator) / float(denominator)
        return parsed if math.isfinite(parsed) and parsed > 0 else 0
    except (ValueError, ZeroDivisionError):
        return 0


def _safe_float(value: object) -> float:
    try:
        parsed = float(value or 0)
        return parsed if math.isfinite(parsed) and parsed > 0 else 0
    except (TypeError, ValueError):
        return 0


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_task_id(value: str | None) -> str:
    raw = (value or uuid.uuid4().hex).strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)[:80] or uuid.uuid4().hex
