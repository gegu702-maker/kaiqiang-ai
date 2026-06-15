from __future__ import annotations

import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

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
SUBTITLE_FONT_CANDIDATES = [
    "Noto Sans CJK SC",
    "Noto Sans CJK",
    "Noto Sans CJK JP",
    "Noto Sans CJK KR",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "WenQuanYi Micro Hei",
    "Microsoft YaHei",
    "Arial Unicode MS",
]

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
    subtitle_text: str | None = None


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\u3130-\u318f\uac00-\ud7af]")
PRIMARY_BREAK_RE = re.compile(r"([。！？!?；;]+)")
SECONDARY_BREAK_RE = re.compile(r"([，,、]+)")


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
    video_path = work_dir / "input.mp4"
    audio_path = work_dir / "input.wav"
    config_path = ROOT / "configs" / "inference" / "generated" / f"{task_id}.yaml"
    result_dir = ROOT / "results" / "api" / task_id

    await _prepare_input(payload.video_url, payload.video_path, video_path, "video")
    await _prepare_input(payload.audio_url, payload.audio_path, audio_path, "audio")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump({"task_0": {"video_path": str(video_path), "audio_path": str(audio_path)}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    async with gpu_lock:
        completed = await asyncio.to_thread(_run_inference, config_path, result_dir)

    final_video = completed
    if (payload.subtitle_text or "").strip():
        final_video = await asyncio.to_thread(_burn_subtitles_into_video, completed, payload.subtitle_text or "", task_id)

    output_path = OUTPUT_ROOT / f"{task_id}.mp4"
    shutil.copy2(final_video, output_path)
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "completed",
        "task_id": task_id,
        "video_url": f"{base_url}/results/{output_path.name}",
        "subtitle_applied": bool((payload.subtitle_text or "").strip()),
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
        raise HTTPException(status_code=500, detail=f"MuseTalk inference failed: {result.stderr[-2000:] or result.stdout[-2000:]}")
    outputs = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    outputs = [item for item in outputs if not item.name.startswith("temp_")]
    if not outputs:
        raise HTTPException(status_code=500, detail="MuseTalk output video missing")
    return outputs[0]


def _burn_subtitles_into_video(input_path: Path, subtitle_text: str, task_id: str) -> Path:
    clean_text = " ".join((subtitle_text or "").replace("\n", " ").split()).strip()
    if not clean_text:
        return input_path

    with tempfile.TemporaryDirectory(prefix=f"subtitle-{task_id}-", dir=str(INPUT_ROOT)) as tmp:
        tmp_path = Path(tmp)
        subtitle_path = tmp_path / "subtitles.ass"
        output_path = tmp_path / "output.mp4"

        metadata = _probe_video(input_path)
        duration = max(0.1, _safe_float(metadata.get("duration")))
        width = max(1, int(metadata.get("width") or 1080))
        height = max(1, int(metadata.get("height") or 1920))
        subtitle_path.write_text(_build_ass(clean_text, duration, width, height), encoding="utf-8-sig")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"{_subtitle_backdrop_filter()},subtitles={_ffmpeg_filter_path(subtitle_path)}",
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
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"subtitle burn failed: {_format_ffmpeg_error(result)}")
        if not output_path.exists():
            raise HTTPException(status_code=500, detail=f"subtitle burn failed: {_format_ffmpeg_error(result, 'ffmpeg output file was not created')}")
        output_bytes = output_path.read_bytes()
        if len(output_bytes) < 1024 or b"ftyp" not in output_bytes[:32]:
            raise HTTPException(status_code=500, detail=f"subtitle burn failed: {_format_ffmpeg_error(result, 'ffmpeg output is not a valid MP4 file')}")

        final_path = INPUT_ROOT / task_id / "final_with_subtitles.mp4"
        shutil.copy2(output_path, final_path)
        return final_path


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
        raise HTTPException(status_code=500, detail=f"ffprobe failed: {result.stderr[-1000:] or result.stdout[-1000:]}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail=f"ffprobe returned invalid JSON: {error}") from error
    stream = (payload.get("streams") or [{}])[0]
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration": (payload.get("format") or {}).get("duration") or stream.get("duration"),
    }


def _build_ass(text: str, duration: float, width: int, height: int) -> str:
    font_size = _font_size(width, height)
    margin_v = max(48, int(height * 0.09))
    outline = max(2, min(3, round(font_size * 0.075)))
    cues = _build_cues(text, duration)
    events = "\n".join(
        f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{_escape_ass_text(lines)}"
        for start, end, lines in cues
    )
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{_font_name()},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H66000000,0,0,0,0,100,100,0,0,1,{outline},1,2,80,80,{margin_v},1

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
    line_limit = 14 if cjk else 32
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


def _font_size(width: int, height: int) -> int:
    short_side = max(1, min(width, height))
    return max(28, min(42, round(short_side * 0.037)))


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _font_name() -> str:
    for candidate in SUBTITLE_FONT_CANDIDATES:
        matched = _fc_match_family(candidate)
        if matched and matched.lower() not in {"dejavu sans", "arial", "sans"}:
            return matched
    return "Noto Sans CJK SC"


def _fc_match_family(font_name: str) -> str:
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family[0]}", font_name],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


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


def _format_ffmpeg_error(result: subprocess.CompletedProcess[str], message: str | None = None) -> str:
    parts = [message or "ffmpeg exited with non-zero status", f"returncode={result.returncode}"]
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        parts.append(f"stdout_tail={stdout[-2000:]}")
    if stderr:
        parts.append(f"stderr_tail={stderr[-4000:]}")
    return "\n".join(parts)


def _subtitle_backdrop_filter() -> str:
    return "drawbox=x=0:y=ih*0.76:w=iw:h=ih*0.24:color=black@0.38:t=fill"


def _ffmpeg_filter_path(path: Path) -> str:
    value = path.as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"'{value}'"


def _ffprobe_path() -> str:
    ffmpeg = Path(FFMPEG_PATH)
    if ffmpeg.name.lower() in {"ffmpeg", "ffmpeg.exe"}:
        suffix = ".exe" if ffmpeg.suffix.lower() == ".exe" else ""
        return str(ffmpeg.with_name(f"ffprobe{suffix}"))
    return FFMPEG_PATH.replace("ffmpeg", "ffprobe")


def _safe_task_id(value: str | None) -> str:
    raw = (value or uuid.uuid4().hex).strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)[:80] or uuid.uuid4().hex
