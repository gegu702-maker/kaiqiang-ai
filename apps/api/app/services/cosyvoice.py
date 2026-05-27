from __future__ import annotations

import logging
import wave
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings


logger = logging.getLogger(__name__)

VOICE_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg"}
VOICE_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/x-aac",
    "audio/mp4a-latm",
    "video/mp4",
    "application/octet-stream",
}
MB = 1024 * 1024


def validate_reference_audio(upload: UploadFile) -> None:
    extension = Path(upload.filename or "reference.wav").suffix.lower()
    if extension not in VOICE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"当前文件格式：{extension.lstrip('.') or 'unknown'}；支持格式：mp3, wav, m4a")
    if upload.content_type not in VOICE_TYPES:
        raise HTTPException(status_code=400, detail=f"当前文件类型：{upload.content_type or 'unknown'}；支持格式：mp3, wav, m4a")


async def read_reference_audio(upload: UploadFile) -> bytes:
    validate_reference_audio(upload)
    content = await upload.read()
    if len(content) > 20 * MB:
        raise HTTPException(status_code=413, detail="参考声音最大支持 20MB")
    return content


async def clone_voice_bytes(
    *,
    text: str,
    reference_audio: UploadFile,
    prompt_text: str | None = None,
) -> tuple[bytes, str, str]:
    if not text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")

    reference_content = await read_reference_audio(reference_audio)
    filename = reference_audio.filename or "reference.wav"
    content_type = reference_audio.content_type or "application/octet-stream"
    reference_content, filename, content_type = _normalize_reference_audio(
        reference_content,
        filename,
        content_type,
    )
    prompt = (prompt_text or "").strip()
    final_text = text.strip()
    logger.warning(
        "CosyVoice upstream zero_shot reference_audio=%s tts_text=%r prompt_text=%r",
        filename,
        final_text,
        prompt,
    )
    print(
        "[CosyVoice upstream zero_shot]",
        {
            "reference_audio": filename,
            "tts_text": final_text,
            "prompt_text": prompt,
        },
        flush=True,
    )

    async with httpx.AsyncClient(timeout=settings.cosyvoice_timeout_seconds, trust_env=False) as client:
        try:
            response = await client.post(
                f"{settings.cosyvoice_url.rstrip('/')}/inference_zero_shot",
                data={
                    "tts_text": final_text,
                    "prompt_text": prompt,
                },
                files={
                    "prompt_wav": (filename, reference_content, content_type),
                },
            )
        except httpx.RequestError as error:
            raise HTTPException(
                status_code=503,
                detail=f"CosyVoice 服务不可用：{error.__class__.__name__}: {error}",
            ) from error

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"CosyVoice 生成失败：{response.text[:300]}",
        )

    content_type = response.headers.get("content-type", "audio/wav")
    audio_bytes = response.content
    extension = ".wav"

    if "audio/wav" in content_type or "audio/x-wav" in content_type:
        extension = ".wav"
    elif "audio/mpeg" in content_type or "audio/mp3" in content_type:
        extension = ".mp3"
    else:
        audio_bytes = _pcm_to_wav(audio_bytes, settings.cosyvoice_sample_rate)
        content_type = "audio/wav"
        extension = ".wav"

    local_path = _write_local_clone(audio_bytes, extension)
    return audio_bytes, local_path, content_type


def _normalize_reference_audio(content: bytes, filename: str, content_type: str) -> tuple[bytes, str, str]:
    extension = Path(filename).suffix.lower()
    if extension in {".wav"} and content_type in {"audio/wav", "audio/x-wav", "audio/wave"}:
        return content, filename, content_type

    input_path: Path | None = None
    output_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=extension or ".audio", delete=False) as source:
            source.write(content)
            input_path = Path(source.name)
        with NamedTemporaryFile(suffix=".wav", delete=False) as target:
            output_path = Path(target.name)

        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True)
        return output_path.read_bytes(), f"{Path(filename).stem or 'reference'}.wav", "audio/wav"
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail="服务器缺少 ffmpeg，无法处理 mp3 / m4a 参考音频。") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.decode("utf-8", errors="ignore").strip()
        raise HTTPException(status_code=400, detail=f"参考声音转换失败，请上传清晰的 mp3 / wav / m4a 文件。{message}") from error
    finally:
        if input_path:
            input_path.unlink(missing_ok=True)
        if output_path:
            output_path.unlink(missing_ok=True)


def _write_local_clone(content: bytes, extension: str) -> str:
    output_dir = Path("tmp") / "cosyvoice"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{uuid4().hex}{extension}"
    path.write_bytes(content)
    return str(path)


def _pcm_to_wav(content: bytes, sample_rate: int) -> bytes:
    with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with wave.open(str(tmp_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(content)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
