import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api import viral as viral_api
from app.core.auth import get_bearer_token
from app.core.supabase import get_supabase
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


class _Upload:
    def __init__(self, chunks, filename="video.mp4"):
        self.filename = filename
        self._chunks = iter(chunks)
        self.closed = False

    async def read(self, _size):
        value = next(self._chunks, b"")
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self):
        self.closed = True


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


@pytest.mark.parametrize("duration", [30.0, 90.0, 119.0, 170.3, 600.0])
def test_short_medium_long_video_keep_full_asr_timeline(monkeypatch, tmp_path: Path, duration: float):
    monkeypatch.setattr(viral_pipeline.settings, "viral_max_video_duration_seconds", 600)
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


def test_video_just_over_configured_limit_is_structured_and_not_processed(monkeypatch, tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(viral_pipeline.settings, "viral_max_video_duration_seconds", 600)

    async def must_not_extract(*_args, **_kwargs):
        raise AssertionError("over-limit video must not enter audio extraction")

    monkeypatch.setattr(viral_pipeline, "extract_audio", must_not_extract)
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
            metadata={"duration": 600.1},
        )
    )

    assert result["ok"] is False
    assert result["code"] == "video_too_long"
    assert result["stage"] == "extracting_audio"
    assert result["retryable"] is False
    assert "600.1" in result["message"] and "600 秒" in result["message"]
    assert result["diagnostic"] == {"actual_duration_seconds": 600.1, "allowed_duration_seconds": 600}


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


def test_public_metadata_full_mode_uses_partial_source_threshold(monkeypatch):
    scripts = [
        "这条公开标题能确认的重点有限，因此这里只分析标题里的反差信息。" * 5,
        "从普通用户角度看，公开信息只说明了话题方向，不能代替完整视频观点。" * 5,
        "从行业角度可以关注标题呈现的趋势，但案例和数据仍需原视频验证。" * 5,
    ]

    async def fake_generate(_self, **_kwargs):
        return {
            **_analysis(150),
            "rewrites": [{"title": f"版本{i}", "script": scripts[i - 1]} for i in range(1, 4)],
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            source_url="https://example.com/video",
            raw_script="平台：douyin\n标题：公开标题包含可验证的话题信息\n时长：167 秒",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
            source_scope="public_metadata",
        )
    )

    assert result["rewrites"]
    assert all(len(item["script"]) >= 120 for item in result["rewrites"])


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


def test_12_7mb_upload_reaches_video_processing(monkeypatch):
    observed = {}
    upload = _Upload([b"x" * (6 * 1024 * 1024), b"y" * (6 * 1024 * 1024), b"z" * 716800])

    async def fake_process(*_args, **kwargs):
        observed["size"] = kwargs["video_path"].stat().st_size
        observed["work_dir"] = kwargs["work_dir"]
        return {"ok": True, "diagnostics": {"video_duration_seconds": 170.0, "asr_coverage_seconds": 170.0}}

    monkeypatch.setattr(viral_pipeline, "_process_video_path", fake_process)
    result = asyncio.run(
        viral_pipeline.run_uploaded_viral_pipeline(
            _Supabase(), upload=upload, user_id="u1", email="u@example.com", source_url="https://example.com", industry="knowledge", language="zh", rewrite_length="full"
        )
    )
    assert result["ok"] is True
    assert observed["size"] == 13_299_712
    assert not observed["work_dir"].exists()
    assert upload.closed is True


def test_oversized_and_interrupted_uploads_return_structured_errors(monkeypatch):
    monkeypatch.setattr(viral_pipeline.settings, "viral_max_download_mb", 1)
    oversized = asyncio.run(
        viral_pipeline.run_uploaded_viral_pipeline(
            _Supabase(), upload=_Upload([b"x" * (1024 * 1024 + 1)]), user_id="u1", email="u@example.com", source_url="", industry="knowledge", language="zh", rewrite_length="full"
        )
    )
    assert oversized["error_code"] == "video_too_large"

    interrupted = asyncio.run(
        viral_pipeline.run_uploaded_viral_pipeline(
            _Supabase(), upload=_Upload([b"ok", OSError("connection lost")]), user_id="u1", email="u@example.com", source_url="", industry="knowledge", language="zh", rewrite_length="full"
        )
    )
    assert interrupted["error_code"] == "upload_interrupted"
    assert "connection lost" in interrupted["fallback_reason"]
    assert interrupted["code"] == "upload_interrupted"
    assert interrupted["stage"] == "pending"
    assert interrupted["retryable"] is True
    assert "request_id" in interrupted


def test_frontend_upload_has_progress_and_structured_network_errors():
    api_source = (Path(__file__).parents[2] / "web" / "lib" / "api.ts").read_text(encoding="utf-8")
    component_source = (Path(__file__).parents[2] / "web" / "components" / "ViralAnalyzerClient.tsx").read_text(encoding="utf-8")
    assert "new XMLHttpRequest()" in api_source
    assert "request.upload.onprogress" in api_source
    assert "network_error" in api_source and "client_timeout" in api_source and "request_aborted" in api_source
    assert 'setRequestHeader("Content-Type"' not in api_source
    assert "上传进度：" in component_source
    assert "文件大小：" in component_source
    assert "仅基于公开信息（非完整拆解）" in component_source
    assert "ASR 模型不可用" in component_source
    assert "AI 响应格式错误" in component_source
    assert "请求 ID：" in component_source
    assert "自动转写稿（AI校正，建议人工复核）" in component_source
    assert "查看原始ASR转写" in component_source
    assert "校正" in component_source
    assert "确认此段" in component_source
    assert "全部确认后继续拆解" in component_source
    assert "SegmentAudioPlayer" in component_source
    assert "continueReviewedViralPipeline" in component_source
    assert "setUploadProgress(null)" in component_source


def test_real_multipart_12_7mb_route_and_cors(monkeypatch):
    observed = {}

    async def fake_pipeline(_supabase, **kwargs):
        observed["filename"] = kwargs["upload"].filename
        observed["size"] = len(await kwargs["upload"].read())
        return {"ok": True, "source_type": "uploaded_video_asr"}

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "run_uploaded_viral_pipeline", fake_pipeline)
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://preview.example"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(viral_api.router, prefix="/api")
    app.dependency_overrides[get_bearer_token] = lambda: "token"
    app.dependency_overrides[get_supabase] = lambda: _Supabase()
    client = TestClient(app)
    preflight = client.options(
        "/api/viral/pipeline/upload",
        headers={
            "Origin": "https://preview.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://preview.example"

    payload = b"x" * 13_299_712
    response = client.post(
        "/api/viral/pipeline/upload",
        headers={"Origin": "https://preview.example", "Authorization": "Bearer token"},
        files={"video_file": ("170-seconds.mp4", payload, "video/mp4")},
        data={"industry": "knowledge", "language": "zh", "rewrite_length": "full"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://preview.example"
    assert observed == {"filename": "170-seconds.mp4", "size": len(payload)}
