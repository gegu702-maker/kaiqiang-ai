import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
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


def test_financial_asr_defaults_to_single_bare_medium_pass():
    assert Settings.model_fields["faster_whisper_model_size"].default == "medium"
    assert Settings.model_fields["faster_whisper_vad_filter"].default is False
    assert Settings.model_fields["faster_whisper_word_timestamps"].default is False
    assert Settings.model_fields["viral_asr_use_initial_prompt"].default is False
    assert Settings.model_fields["viral_asr_use_hotwords"].default is False


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
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_initial_prompt", True)
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_hotwords", True)
    monkeypatch.setattr(asr_service.settings, "faster_whisper_vad_filter", True)
    result = asr_service._transcribe_with_faster_whisper(audio, "zh")

    assert result.ok is True
    assert observed["language"] == "zh"
    assert observed["beam_size"] == 5
    assert observed["vad_filter"] is True
    assert observed["initial_prompt"] == FINANCIAL_INITIAL_PROMPT
    assert observed["hotwords"] == FINANCIAL_HOTWORDS


def test_word_timestamps_split_review_windows_to_original_asr_chunks():
    words = [
        SimpleNamespace(start=0.0, end=2.0, word="中国"),
        SimpleNamespace(start=2.0, end=4.0, word="人保。"),
        SimpleNamespace(start=4.0, end=7.0, word="沪深"),
        SimpleNamespace(start=7.0, end=9.0, word="300"),
    ]
    chunks = asr_service._split_transcription_segment(
        SimpleNamespace(start=0, end=9, text="中国人保。沪深300", words=words)
    )
    assert [(item.start, item.end, item.text) for item in chunks] == [
        (0.0, 4.0, "中国人保。"),
        (4.0, 9.0, "沪深300"),
    ]


def test_missing_word_timestamps_are_split_into_bounded_review_windows():
    text = "这是一段没有词级时间戳但必须完整保留的财经转写内容。" * 8
    chunks = asr_service._split_transcription_segment(
        SimpleNamespace(start=36.5, end=66.5, text=text, words=None)
    )

    assert "".join(item.text for item in chunks) == text
    assert max(item.end - item.start for item in chunks) <= 8.0
    assert chunks[0].start == 36.5
    assert chunks[-1].end == 66.5


def test_low_density_asr_retries_without_vad_and_uses_complete_pass(monkeypatch, tmp_path: Path):
    calls = []
    sparse = "财" * 151
    complete = "金融市场完整转写" * 112

    class _Model:
        def transcribe(self, _path, **kwargs):
            calls.append(kwargs)
            text = sparse if kwargs["vad_filter"] else complete
            return iter([SimpleNamespace(start=0, end=170.333, text=text, words=None)]), SimpleNamespace()

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    monkeypatch.setattr(asr_service, "_get_model", lambda: _Model())
    monkeypatch.setattr(asr_service.settings, "viral_asr_domain", "financial")
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_initial_prompt", True)
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_hotwords", True)
    monkeypatch.setattr(asr_service.settings, "faster_whisper_vad_filter", True)
    monkeypatch.setattr(asr_service.settings, "faster_whisper_word_timestamps", True)

    result = asr_service._transcribe_with_faster_whisper(audio, "zh", 170.333)

    assert result.ok is True
    assert result.recovery_attempted is True
    assert result.recovery_used is True
    assert calls[0]["vad_filter"] is True
    assert calls[1]["vad_filter"] is False
    assert calls[0]["word_timestamps"] is True
    assert calls[1]["word_timestamps"] is False
    assert result.coverage_seconds == 170.333
    assert len(result.transcript.replace("\n", "")) == len(complete)
    assert max(segment.end - segment.start for segment in result.segments or []) <= 8.0


def test_default_business_asr_is_exactly_one_bare_a_pass(monkeypatch, tmp_path: Path):
    calls = []

    class _Model:
        def transcribe(self, _path, **kwargs):
            calls.append(kwargs)
            return iter([SimpleNamespace(start=0, end=167.6, text="财经完整正文" * 100, words=None)]), SimpleNamespace()

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    monkeypatch.setattr(asr_service, "_get_model", lambda: _Model())
    monkeypatch.setattr(asr_service.settings, "viral_asr_domain", "financial")
    monkeypatch.setattr(asr_service.settings, "faster_whisper_vad_filter", False)
    monkeypatch.setattr(asr_service.settings, "faster_whisper_word_timestamps", False)
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_initial_prompt", False)
    monkeypatch.setattr(asr_service.settings, "viral_asr_use_hotwords", False)

    result = asr_service._transcribe_with_faster_whisper(audio, "zh", 170.333)

    assert result.ok is True
    assert len(calls) == 1
    assert calls[0]["vad_filter"] is False
    assert calls[0]["word_timestamps"] is False
    assert "initial_prompt" not in calls[0]
    assert "hotwords" not in calls[0]


def test_word_timestamp_context_merges_china_ping_an_before_residual_review():
    source = [
        SimpleNamespace(
            start=57.9,
            end=61.0,
            text="中国平安发布公告。",
            words=[
                SimpleNamespace(start=57.9, end=58.0, word="中国平"),
                SimpleNamespace(start=58.0, end=58.4, word="安"),
                SimpleNamespace(start=58.4, end=61.0, word="发布公告。"),
            ],
        )
    ]

    segments, transcript, coverage, *_diagnostics = asr_service._normalize_transcription(iter(source))

    assert "中国平安" in transcript
    assert coverage == 61.0
    assert all(segment.text != "中国平" for segment in segments)
    assert max(segment.end - segment.start for segment in segments) <= 8.0


def test_pathological_word_timestamp_is_split_into_review_safe_intervals():
    source = [
        SimpleNamespace(
            start=74.4,
            end=101.9,
            text="中国平安的公开信息需要结合完整上下文审慎复核。",
            words=[
                SimpleNamespace(
                    start=74.4,
                    end=101.9,
                    word="中国平安的公开信息需要结合完整上下文审慎复核。",
                )
            ],
        )
    ]

    segments, transcript, coverage, *_diagnostics = asr_service._normalize_transcription(iter(source))

    assert transcript.replace("\n", "") == source[0].text
    assert coverage == 101.9
    assert len(segments) == 4
    assert max(segment.end - segment.start for segment in segments) <= 8.0


def test_sparse_word_timestamps_do_not_discard_complete_segment_text():
    full_text = "财经市场的完整观点和论据需要保留，不能因为词级时间戳稀疏而丢失正文。" * 8
    source = SimpleNamespace(
        start=0,
        end=64,
        text=full_text,
        words=[SimpleNamespace(start=0, end=64, word="财经市场")],
    )

    chunks = asr_service._split_transcription_segment(source)

    assert "".join(item.text for item in chunks) == full_text
    assert max(item.end - item.start for item in chunks) <= 8.0


def test_nearly_complete_word_timestamps_never_replace_canonical_segment_text():
    full_text = "完整segment正文必须保留最后这部分论据。"
    source = SimpleNamespace(
        start=0,
        end=12,
        text=full_text,
        words=[
            SimpleNamespace(start=0, end=5, word="完整segment正文必须保留"),
            SimpleNamespace(start=5, end=9, word="最后这部分"),
        ],
    )

    chunks = asr_service._split_transcription_segment(source)

    assert "".join(item.text for item in chunks) == full_text
    assert max(item.end - item.start for item in chunks) <= 8.0


def test_asr_generator_is_fully_consumed_once_and_preserves_all_segment_text():
    source_texts = ["第一段完整正文。", "第二段完整正文。", "第三段完整正文。"]
    yielded = []

    def source():
        for index, text in enumerate(source_texts):
            yielded.append(index)
            yield SimpleNamespace(start=index * 10, end=(index + 1) * 10, text=text, words=None)

    segments, transcript, coverage, raw_count, raw_chars, *_diagnostics = asr_service._normalize_transcription(source())

    assert yielded == [0, 1, 2]
    assert raw_count == 3
    assert raw_chars == sum(len(text) for text in source_texts)
    assert "".join(segment.text for segment in segments) == "".join(source_texts)
    assert transcript.replace("\n", "") == "".join(source_texts)
    assert coverage == 30


def test_unicode_replacement_is_removed_and_exact_segment_requires_review(monkeypatch):
    async def no_changes(_self, **_kwargs):
        return {"segments": []}

    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", no_changes)
    segments = [ASRSegment(0, 4, "中国人保回购。"), ASRSegment(4, 7.5, "沪深�指数。")]
    result = asyncio.run(financial_transcript.correct_financial_transcript(segments))

    assert "�" not in result.corrected_transcript
    assert result.quality_passed is False
    assert len(result.review_segments) == 1
    assert result.review_segments[0]["segment_index"] == 1
    assert result.review_segments[0]["start"] == 4
    assert result.review_segments[0]["end"] == 7.5


def test_safe_repeated_phrase_is_deduplicated_and_truncated_sentence_is_reviewed(monkeypatch):
    async def no_changes(_self, **_kwargs):
        return {"segments": []}

    monkeypatch.setattr(financial_transcript.LLMProvider, "generate_json", no_changes)
    result = asyncio.run(
        financial_transcript.correct_financial_transcript(
            [ASRSegment(0, 3, "市场持续回暖市场持续回暖。"), ASRSegment(3, 6, "保险机构增持因为")]
        )
    )

    assert result.corrected_segments[0].text == "市场持续回暖。"
    assert result.review_segments[0]["segment_index"] == 1
    assert "句尾疑似截断" in result.review_segments[0]["reason"]


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
        observed["effective_speech_seconds"] = kwargs["effective_speech_seconds"]
        observed["source_fact_sentences"] = kwargs["source_fact_sentences"]
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
    assert observed["effective_speech_seconds"] == 5
    assert observed["source_fact_sentences"][0]["source_segment_indexes"] == [0]
    assert "transcript" not in result
    assert "raw_transcript" not in result
    assert result["diagnostics"]["correction_count"] == 3
    assert result["diagnostics"]["normalization_validation_passed"] is True
    assert result["diagnostics"]["normalized_fact_count"] == 1


def _legacy_review_continue_blocks_unconfirmed_and_uses_human_text(monkeypatch):
    context = {
        "request_id": "viral_original",
        "raw_transcript": "中国人宝回购。\n沪深�指数。",
        "raw_timeline": [
            {"segment_index": 0, "start": 0, "end": 3, "timestamp": "00:00–00:03", "text": "中国人宝回购。"},
            {"segment_index": 1, "start": 3, "end": 6, "timestamp": "00:03–00:06", "text": "沪深�指数。"},
        ],
        "suggested_timeline": [
            {"segment_index": 0, "start": 0, "end": 3, "timestamp": "00:00–00:03", "text": "中国人保回购。"},
            {"segment_index": 1, "start": 3, "end": 6, "timestamp": "00:03–00:06", "text": "沪深指数。"},
        ],
        "review_indices": [1],
        "global_review_reasons": [],
        "metadata": {"duration": 6},
        "diagnostics": {"video_duration_seconds": 6, "asr_coverage_seconds": 6, "segment_count": 2},
        "source_type": "uploaded_video_asr",
        "corrections": [],
    }
    monkeypatch.setattr(viral_pipeline.settings, "viral_review_signing_secret", "test-review-secret")
    token = create_review_token(context)
    blocked = asyncio.run(
        viral_pipeline._legacy_review_continuation_not_exposed(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            review_context=context,
            review_token=token,
            confirmed_segments=[],
            source_url="",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )
    assert blocked["error_code"] == "review_segments_unconfirmed"

    observed = {}

    async def fake_analysis(_supabase, **kwargs):
        observed["raw_script"] = kwargs["raw_script"]
        return _analysis()

    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", fake_analysis)
    completed = asyncio.run(
        viral_pipeline._legacy_review_continuation_not_exposed(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            review_context=context,
            review_token=token,
            confirmed_segments=[{"segment_index": 1, "corrected_text": "沪深300指数。", "confirmed": True}],
            source_url="",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )
    assert completed["ok"] is True
    assert observed["raw_script"] == "中国人保回购。\n沪深300指数。"
    assert completed["correction_audit"][-1]["source"] == "human_confirmed"
    assert completed["correction_audit"][-1]["confirmed"] is True
