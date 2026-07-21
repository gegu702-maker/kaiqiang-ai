from __future__ import annotations

import asyncio
import importlib.util
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.api import avatar
from app.services import musetalk_client
from app.services.subtitles import (
    MediaDurationError,
    SubtitleSegment,
    burn_subtitles_to_video,
    probe_media_info,
    write_ass_file,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FFMPEG = shutil.which("ffmpeg")

pytestmark = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is required for media duration regression tests")


@pytest.fixture(scope="module")
def autodl_service(tmp_path_factory):
    root = tmp_path_factory.mktemp("musetalk-root")
    output = tmp_path_factory.mktemp("musetalk-output")
    inputs = tmp_path_factory.mktemp("musetalk-input")
    import os

    previous = {
        key: os.environ.get(key)
        for key in ("MUSETALK_ROOT", "MUSETALK_OUTPUT_ROOT", "MUSETALK_INPUT_ROOT")
    }
    os.environ["MUSETALK_ROOT"] = str(root)
    os.environ["MUSETALK_OUTPUT_ROOT"] = str(output)
    os.environ["MUSETALK_INPUT_ROOT"] = str(inputs)
    try:
        module_path = REPO_ROOT / "autodl" / "musetalk_service.py"
        spec = importlib.util.spec_from_file_location("p236_musetalk_service", module_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]


def _make_video(path: Path, *, rate: str, duration: float) -> None:
    _run(
        [
            FFMPEG or "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=160x120:r={rate}:d={duration}",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def _make_speech_fixture(path: Path) -> None:
    _run(
        [
            FFMPEG or "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=0.5",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono:d=0.4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=16000:duration=1.1",
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def _make_muxed_video(path: Path, *, video_duration: float, audio_duration: float, fps: int = 30) -> None:
    _run(
        [
            FFMPEG or "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:s=160x120:r={fps}:d={video_duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=550:sample_rate=16000:duration={audio_duration}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ]
    )


def _rms(path: Path, start: float, end: float) -> float:
    with wave.open(str(path), "rb") as wav:
        assert wav.getsampwidth() == 2
        rate = wav.getframerate()
        wav.setpos(round(start * rate))
        frames = wav.readframes(round((end - start) * rate))
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    return math.sqrt(sum(sample * sample for sample in samples) / max(len(samples), 1))


@pytest.mark.parametrize(
    ("rate", "expected_fps", "copied"),
    [
        ("3726/125", 30, False),  # 29.808
        ("14880/499", 30, False),  # 29.819639...
        ("30000/1001", 30, False),  # 29.970029...
        ("25", 25, True),
        ("30", 30, True),
    ],
)
def test_wrapper_normalizes_fractional_fps_to_stable_cfr(
    tmp_path: Path,
    autodl_service,
    rate: str,
    expected_fps: int,
    copied: bool,
):
    source = tmp_path / f"source-{rate.replace('/', '-')}.mp4"
    prepared = tmp_path / f"prepared-{rate.replace('/', '-')}.mp4"
    _make_video(source, rate=rate, duration=1.2)

    source_media = autodl_service._probe_media(source)
    target = autodl_service._select_cfr_fps(source_media)
    autodl_service._prepare_cfr_video(source, prepared, source_media, target)
    prepared_media = autodl_service._probe_media(prepared)

    assert target == expected_fps
    assert prepared_media["is_cfr"] is True
    assert prepared_media["fps"] == pytest.approx(expected_fps, abs=0.001)
    assert (prepared.read_bytes() == source.read_bytes()) is copied


@pytest.mark.parametrize(
    "video_duration",
    [1.0, 2.4, 3.0],
    ids=["video-shorter", "approximately-equal", "video-longer"],
)
def test_audio_frame_budget_covers_source_plus_tail_for_all_video_relations(
    tmp_path: Path,
    autodl_service,
    video_duration: float,
):
    video = tmp_path / f"video-{video_duration}.mp4"
    audio = tmp_path / f"audio-{video_duration}.wav"
    working = tmp_path / f"working-{video_duration}.wav"
    _make_video(video, rate="30000/1001", duration=video_duration)
    _make_speech_fixture(audio)

    target_fps = autodl_service._select_cfr_fps(autodl_service._probe_media(video))
    original = autodl_service._probe_media(audio)
    tail_padding = autodl_service._calculate_working_audio_padding(
        original_duration=original["audio_duration"],
        target_fps=target_fps,
    )
    autodl_service._prepare_working_audio(
        audio,
        working,
        tail_padding_seconds=tail_padding,
    )
    prepared = autodl_service._probe_media(working)
    projected_frames = math.floor(prepared["audio_duration"] * target_fps)
    projected_duration = projected_frames / target_fps

    assert prepared["audio_duration"] >= original["audio_duration"] + 0.4
    assert projected_duration + 0.001 >= original["audio_duration"] + 0.4


def test_production_regression_duration_budget_covers_original_1812_seconds(autodl_service):
    padding = autodl_service._calculate_working_audio_padding(original_duration=18.12, target_fps=30)
    working_duration = 18.12 + padding
    projected_frames = math.floor(working_duration * 30)

    assert padding >= 0.4
    assert padding < 0.4 + (1 / 30) + (1 / 16000)
    assert projected_frames == 556
    assert projected_frames / 30 >= 18.52


@pytest.mark.parametrize(
    "script",
    [
        "你好，这是中文合成测试资产。",
        "Hello, this is an English synthetic fixture.",
        "こんにちは、これは日本語の合成テスト素材です。",
    ],
    ids=["chinese", "english", "japanese"],
)
def test_synthetic_language_assets_preserve_internal_pause_and_final_052_seconds(
    tmp_path: Path,
    autodl_service,
    script: str,
):
    source = tmp_path / f"source-{len(script)}.wav"
    working = tmp_path / f"working-{len(script)}.wav"
    _make_speech_fixture(source)
    source_media = autodl_service._probe_media(source)
    tail_padding = autodl_service._calculate_working_audio_padding(
        original_duration=source_media["audio_duration"],
        target_fps=30,
    )
    autodl_service._prepare_working_audio(source, working, tail_padding_seconds=tail_padding)

    working_media = autodl_service._probe_media(working)
    assert source_media["audio_duration"] == pytest.approx(2.0, abs=0.002)
    assert working_media["audio_duration"] >= 2.4
    assert _rms(working, 0.55, 0.8) < 10  # Internal pause remains; it does not terminate processing.
    assert _rms(working, 1.48, 2.0) > 1000  # The final 0.52 seconds remain audible.
    assert _rms(working, 2.05, 2.35) < 10  # Required tail padding is silent.


def test_subtitle_burn_preserves_aligned_audio_without_shortest(tmp_path: Path):
    source = tmp_path / "aligned.mp4"
    ass = tmp_path / "subtitle.ass"
    output = tmp_path / "captioned.mp4"
    _make_muxed_video(source, video_duration=2.4, audio_duration=2.4)
    write_ass_file([SubtitleSegment(start=0, end=2.4, lines=["时长回归测试"])], ass, video_width=160, video_height=120)

    burn_subtitles_to_video(source, ass, output, FFMPEG)

    source_media = probe_media_info(source, FFMPEG)
    output_media = probe_media_info(output, FFMPEG)
    assert output.exists()
    assert output_media.audio_duration is not None
    assert source_media.audio_duration is not None
    assert abs(output_media.video_duration - output_media.audio_duration) <= output_media.frame_duration + 0.001
    assert source_media.audio_duration - output_media.audio_duration <= output_media.frame_duration + 0.001


def test_subtitle_burn_rejects_video_shorter_than_audio_and_writes_no_output(tmp_path: Path):
    source = tmp_path / "short-video.mp4"
    ass = tmp_path / "subtitle.ass"
    output = tmp_path / "must-not-exist.mp4"
    _make_muxed_video(source, video_duration=1.0, audio_duration=1.52)
    write_ass_file([SubtitleSegment(start=0, end=1.0, lines=["不得截断"])], ass, video_width=160, video_height=120)

    with pytest.raises(MediaDurationError) as captured:
        burn_subtitles_to_video(source, ass, output, FFMPEG)

    assert captured.value.detail["code"] == "avatar_video_shorter_than_audio"
    assert captured.value.detail["stage"] == "subtitle_input"
    assert not output.exists()


def test_musetalk_duration_guard_prevents_upload(monkeypatch, tmp_path: Path):
    source = tmp_path / "short-musetalk-output.mp4"
    _make_muxed_video(source, video_duration=1.0, audio_duration=1.52)
    content = source.read_bytes()
    upload_calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return httpx.Response(
                200,
                json={"status": "completed", "video_url": "https://musetalk.test/results/task.mp4"},
            )

        async def get(self, *_args, **_kwargs):
            return httpx.Response(200, content=content, headers={"content-type": "video/mp4"})

    monkeypatch.setattr(musetalk_client.httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(musetalk_client.settings, "muse_talk_api_base_url", "https://musetalk.test")
    monkeypatch.setattr(musetalk_client, "upload_public_bytes", lambda *_args, **_kwargs: upload_calls.append(True))

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            musetalk_client.generate_avatar_video_with_musetalk(
                object(),
                video_url="https://storage.test/video.mp4",
                audio_url="https://storage.test/audio.wav",
                task_id="duration-guard-test",
                script_text="不得生成残缺文件",
            )
        )

    assert captured.value.detail["code"] == "avatar_video_shorter_than_audio"
    assert captured.value.detail["stage"] == "musetalk_output"
    assert upload_calls == []


def test_duration_failure_does_not_complete_task_or_record_usage(monkeypatch):
    updates = []
    failed = []
    usage = []

    async def ready(*_args, **_kwargs):
        return {"status": "ready"}

    async def duration_failure(*_args, **_kwargs):
        raise HTTPException(
            status_code=502,
            detail={"code": "avatar_video_shorter_than_audio", "stage": "musetalk_output"},
        )

    monkeypatch.setattr(avatar, "get_supabase", lambda: object())
    monkeypatch.setattr(avatar, "ensure_gpu_ready", ready)
    monkeypatch.setattr(avatar, "generate_avatar_video_with_musetalk", duration_failure)
    monkeypatch.setattr(avatar, "_update_avatar_task", lambda _db, _task_id, values: updates.append(values))
    monkeypatch.setattr(avatar, "_safe_fail_task", lambda _db, task_id, detail: failed.append((task_id, detail)))
    monkeypatch.setattr(avatar, "log_generation_usage", lambda *_args, **_kwargs: usage.append(True))

    asyncio.run(
        avatar._process_avatar_task(
            "duration-failure-task",
            "synthetic-user",
            "https://storage.test/video.mp4",
            "https://storage.test/audio.wav",
            "synthetic script",
        )
    )

    assert all(update.get("status") != "completed" for update in updates)
    assert failed and failed[0][0] == "duration-failure-task"
    assert usage == []
