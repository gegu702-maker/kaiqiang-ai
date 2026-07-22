import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.asr_service import ASRResult, ASRSegment
from app.services import viral_analyzer, viral_pipeline


class _Table:
    def insert(self, _payload):
        return self

    def update(self, _payload):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _Supabase:
    def table(self, _name):
        return _Table()


def _analysis(script_size=140):
    script = "信息具体。" * (script_size // 5)
    return {
        "project_id": "project-1",
        "topic": "长视频主题",
        "hook": "开头钩子",
        "selling_points": ["爆点1", "爆点2", "爆点3", "爆点4"],
        "structure": ["开头", "观点", "论据", "案例", "结尾"],
        "template": "钩子+观点+论据+案例+结论",
        "core_points": ["核心观点"],
        "arguments": ["完整论据"],
        "cases": ["具体案例"],
        "data_points": ["数据 42"],
        "rewrites": [{"title": f"版本{i}", "script": script} for i in range(1, 4)],
        "diagnostics": {"prompt_input_chars": 7000},
    }


@pytest.mark.parametrize("duration", [30.0, 90.0, 170.333])
def test_short_medium_long_video_keep_full_asr_timeline(monkeypatch, tmp_path: Path, duration: float):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(viral_pipeline, "extract_audio", lambda *_args: asyncio.sleep(0, result=tmp_path / "audio.wav"))
    monkeypatch.setattr(
        viral_pipeline,
        "transcribe_audio",
        lambda *_args: asyncio.sleep(
            0,
            result=ASRResult(
                ok=True,
                transcript="第一段完整内容\n第二段完整内容",
                segments=[ASRSegment(0, duration / 2, "第一段完整内容"), ASRSegment(duration / 2, duration, "第二段完整内容")],
                coverage_seconds=duration,
            ),
        ),
    )
    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", lambda *_args, **_kwargs: asyncio.sleep(0, result=_analysis()))

    result = asyncio.run(
        viral_pipeline._process_video_path(
            _Supabase(),
            video_path=video,
            work_dir=tmp_path,
            user_id="u1",
            email="u@example.com",
            source_url="",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
            source_type="uploaded_video_asr",
            metadata={"duration": duration},
        )
    )

    assert result["ok"] is True
    assert result["transcript"].endswith("第二段完整内容")
    assert len(result["timeline"]) == 2
    assert result["diagnostics"]["asr_coverage_seconds"] == pytest.approx(duration, abs=0.001)
    assert result["degraded"] is False


def test_partial_asr_is_explicit_and_complete_failure_stops(monkeypatch, tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(viral_pipeline, "extract_audio", lambda *_args: asyncio.sleep(0, result=tmp_path / "audio.wav"))
    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", lambda *_args, **_kwargs: asyncio.sleep(0, result=_analysis()))
    monkeypatch.setattr(
        viral_pipeline,
        "transcribe_audio",
        lambda *_args: asyncio.sleep(0, result=ASRResult(ok=True, transcript="只有开头", segments=[ASRSegment(0, 40, "只有开头")], coverage_seconds=40)),
    )
    kwargs = dict(
        video_path=video,
        work_dir=tmp_path,
        user_id="u1",
        email="u@example.com",
        source_url="",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        source_type="uploaded_video_asr",
        metadata={"duration": 170.0},
    )
    partial = asyncio.run(viral_pipeline._process_video_path(_Supabase(), **kwargs))
    assert partial["ok"] is True and partial["degraded"] is True
    assert "40.0/170.0" in partial["warning"]

    monkeypatch.setattr(viral_pipeline, "transcribe_audio", lambda *_args: asyncio.sleep(0, result=ASRResult(ok=False, fallback_reason="ASR provider failed")))
    failed = asyncio.run(viral_pipeline._process_video_path(_Supabase(), **kwargs))
    assert failed["ok"] is False
    assert failed["error_code"] == "asr_failed"
    assert failed["fallback_reason"] == "ASR provider failed"


def test_long_transcript_uses_every_chunk_and_full_rewrite_is_longer(monkeypatch):
    transcript = "甲" * 5000 + "乙" * 5000 + "丙" * 700
    seen_chunks = []

    async def fake_generate(_self, *, payload, **_kwargs):
        if "transcript_chunk" in payload:
            seen_chunks.append(payload["transcript_chunk"])
            return {"summary": f"段落{payload['part']}摘要：" + payload["transcript_chunk"][:20]}
        full = any("完整版" in item for item in payload["requirements"])
        size = 650 if full else 150
        scripts = [
            "。".join(f"观察编号{index}呈现用户需求变化" for index in range(size // 10)),
            "。".join(f"案例序号{index}说明产品应用场景" for index in range(size // 10)),
            "。".join(f"数据批次{index}支持市场趋势判断" for index in range(size // 10)),
        ]
        return {
            **_analysis(size),
            "rewrites": [{"title": f"版本{i}", "script": scripts[i - 1]} for i in range(1, 4)],
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    common = dict(supabase=_Supabase(), user_id="u1", email="u@example.com", raw_script=transcript, industry="knowledge", language="zh")
    full = asyncio.run(viral_analyzer.analyze_viral_script(**common, rewrite_length="full"))
    short = asyncio.run(viral_analyzer.analyze_viral_script(**common, rewrite_length="short"))

    assert "".join(seen_chunks[:3]) == transcript
    assert full["diagnostics"]["hierarchical_chunk_count"] == 3
    assert len(full["rewrites"][0]["script"]) > len(short["rewrites"][0]["script"]) * 2


def test_link_download_is_attempted_before_metadata_fallback(monkeypatch, tmp_path: Path):
    called = []
    monkeypatch.setattr(
        viral_pipeline,
        "resolve_video_link",
        lambda _url: asyncio.sleep(0, result={"ok": True, "downloadable": True, "title": "足够长的公开标题", "description": "足够长的公开描述会触发旧版提前返回", "duration": 30}),
    )
    monkeypatch.setattr(
        viral_pipeline,
        "download_video",
        lambda *_args: asyncio.sleep(0, result=SimpleNamespace(ok=True, video_path=tmp_path / "v.mp4", title="", description="", duration=30, thumbnail="", webpage_url="https://example.com/v")),
    )

    async def fake_process(*_args, **_kwargs):
        called.append("video")
        return {"ok": True, "source_type": "link_video_asr"}

    monkeypatch.setattr(viral_pipeline, "_process_video_path", fake_process)
    result = asyncio.run(
        viral_pipeline.run_viral_pipeline(_Supabase(), user_id="u1", email="u@example.com", source_url="https://example.com/v", industry="knowledge", language="zh")
    )
    assert result["source_type"] == "link_video_asr"
    assert called == ["video"]


def test_frontend_upload_branch_sends_real_file_before_link_pipeline():
    source = (Path(__file__).parents[2] / "web" / "components" / "ViralAnalyzerClient.tsx").read_text(encoding="utf-8")
    upload_branch = source.index("if (videoFile)")
    link_branch = source.index("if (linkCandidate && !hasManualScript)")
    assert upload_branch < link_branch
    assert 'formData.set("video_file", videoFile)' in source
    assert "runUploadedViralPipeline(formData" in source
