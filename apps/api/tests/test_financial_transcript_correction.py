import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.services import asr_service, financial_transcript, viral_pipeline
from app.services.asr_service import ASRResult, ASRSegment
from app.services.financial_terms import FINANCIAL_HOTWORDS, FINANCIAL_INITIAL_PROMPT, FINANCIAL_TERM_CORRECTIONS


class _Table:
    def insert(self, _payload):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _Supabase:
    def table(self, _name):
        return _Table()


def _analysis():
    return {
        "project_id": "p1",
        "topic": "资本市场",
        "hook": "市场为何波动",
        "selling_points": ["观点1", "观点2", "观点3", "观点4"],
        "structure": ["开头", "观点", "论据", "案例", "结尾"],
        "template": "钩子+观点+证据+结论",
        "core_points": ["核心观点"],
        "arguments": ["论据"],
        "cases": [],
        "data_points": [],
        "rewrites": [{"title": f"版本{i}", "script": "资本市场需要结合公开信息审慎判断。" * 20} for i in range(1, 4)],
        "diagnostics": {"prompt_input_chars": 1000},
    }


def test_confirmed_financial_regression_terms_are_corrected(monkeypatch):
    async def no_extra_changes(_self, **_kwargs):
        return {"segments": []}

    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", no_extra_changes)
    raw = "；".join(source for source, _target in FINANCIAL_TERM_CORRECTIONS)
    result = asyncio.run(financial_transcript.correct_financial_transcript([ASRSegment(0, 30, raw)]))

    for source, target in FINANCIAL_TERM_CORRECTIONS:
        assert source not in result.corrected_transcript
        assert target in result.corrected_transcript
    assert result.quality_passed is True
    assert len(result.corrections) == len(FINANCIAL_TERM_CORRECTIONS)


def test_constrained_correction_cannot_change_correct_number_or_entity(monkeypatch):
    original = "中国人保计划投入10亿元进行股份回购。"

    async def unsafe_change(_self, **_kwargs):
        return {
            "segments": [
                {
                    "segment_index": 0,
                    "original_text": original,
                    "corrected_text": "中国平安计划投入20亿元进行股份回购。",
                    "changes": [
                        {"from": "中国人保", "to": "中国平安", "type": "entity", "reason": "猜测"},
                        {"from": "10", "to": "20", "type": "number_format", "reason": "猜测"},
                    ],
                    "review_required": False,
                }
            ]
        }

    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", unsafe_change)
    result = asyncio.run(financial_transcript.correct_financial_transcript([ASRSegment(0, 5, original)]))

    assert result.corrected_transcript == original
    assert result.quality_passed is False
    assert result.review_segments[0]["reason"] == "数字内容发生变化"


def test_sensitive_residual_requires_review(monkeypatch):
    async def no_changes(_self, **_kwargs):
        return {"segments": []}

    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", no_changes)
    result = asyncio.run(financial_transcript.correct_financial_transcript([ASRSegment(0, 5, "大家现在都有习近平。")]))

    assert result.quality_passed is False
    assert "习近平" in result.review_segments[-1]["reason"]


def test_faster_whisper_financial_prompt_and_hotwords(monkeypatch, tmp_path: Path):
    observed = {}

    class _Model:
        def transcribe(self, _path, **kwargs):
            observed.update(kwargs)
            return iter([SimpleNamespace(start=0, end=3, text="中国人保回购")]), SimpleNamespace()

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    monkeypatch.setattr(asr_service, "_get_model", lambda: _Model())
    monkeypatch.setattr(asr_service.settings, "viral_asr_domain", "financial")
    result = asr_service._transcribe_with_faster_whisper(audio, "zh")

    assert result.ok is True
    assert observed["language"] == "zh"
    assert observed["beam_size"] == 5
    assert observed["vad_filter"] is True
    assert observed["initial_prompt"] == FINANCIAL_INITIAL_PROMPT
    assert observed["hotwords"] == FINANCIAL_HOTWORDS


def test_downstream_analysis_uses_corrected_transcript(monkeypatch, tmp_path: Path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    raw = "中国人宝在关键卖点投下新人票。"
    observed = {}

    async def no_extra_changes(_self, **_kwargs):
        return {"segments": []}

    async def fake_analysis(_supabase, **kwargs):
        observed["raw_script"] = kwargs["raw_script"]
        return _analysis()

    monkeypatch.setattr(viral_pipeline.settings, "viral_asr_domain", "financial")
    monkeypatch.setattr(viral_pipeline, "extract_audio", lambda *_args: asyncio.sleep(0, result=audio))
    monkeypatch.setattr(
        viral_pipeline,
        "transcribe_audio",
        lambda *_args: asyncio.sleep(0, result=ASRResult(ok=True, transcript=raw, segments=[ASRSegment(0, 5, raw)], coverage_seconds=5)),
    )
    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", no_extra_changes)
    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", fake_analysis)
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
            metadata={"duration": 5},
        )
    )

    assert result["ok"] is True
    assert observed["raw_script"] == "中国人保在关键节点投下信心票。"
    assert result["transcript"] == observed["raw_script"]
    assert result["raw_transcript"] == raw
    assert result["correction_count"] == 3
