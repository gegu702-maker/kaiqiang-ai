from __future__ import annotations

import asyncio
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
        raise HTTPException(status_code=500, detail=f"MuseTalk inference failed: {result.stderr[-2000:] or result.stdout[-2000:]}")
    outputs = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    outputs = [item for item in outputs if not item.name.startswith("temp_")]
    if not outputs:
        raise HTTPException(status_code=500, detail="MuseTalk output video missing")
    return outputs[0]


def _safe_task_id(value: str | None) -> str:
    raw = (value or uuid.uuid4().hex).strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)[:80] or uuid.uuid4().hex
