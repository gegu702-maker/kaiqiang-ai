import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api import viral as viral_api
from app.core.auth import get_bearer_token
from app.core.supabase import get_supabase
from app.services.asr_service import ASRResult, ASRSegment
from app.services import viral_analyzer, viral_diagnostics, viral_pipeline
from app.services.viral_idempotency import InMemoryIdempotencyStore, viral_analysis_idempotency


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


def _analysis_with_lengths(lengths):
    result = _analysis()
    result["rewrites"] = [
        {"title": f"版本{index + 1}", "script": chr(ord("甲") + index) * length + "。"}
        for index, length in enumerate(lengths)
    ]
    return result


def _preserve_analysis_lengths(payload, *, language):
    del language
    return payload


def test_long_valid_rewrites_are_not_replaced_when_body_mentions_structure():
    payload = _analysis()
    payload["rewrites"] = [
        {
            "title": "版本A：热点反差版",
            "script": "你以为这只是价格变化，其实库存和现金流才是关键。这段内容的结构是先看需求，再看供给，最后检查风险。" + "甲方公开信息说明经营条件仍在变化。" * 24,
        },
        {
            "title": "版本B：用户痛点版",
            "script": "如果你在做内容，不要只复述结果。更实用的结构是解释用户为什么犹豫，再核对现场数据字段和JSON接口。" + "乙方需要结合适用条件逐项判断。" * 24,
        },
        {
            "title": "版本C：商业机会版",
            "script": "站在经营者视角，供应链变化不能只看一次销量。这段论证的结构是库存、周转、售后和现金流。" + "丙方应同时记录机会、成本和止损条件。" * 24,
        },
    ]

    result = viral_analyzer.validate_viral_analysis_payload(payload, language="zh")

    assert all(viral_analyzer._cjk_len(item["script"]) > 300 for item in result["rewrites"])
    assert all("公开信息" in item["script"] or "适用条件" in item["script"] or "止损条件" in item["script"] for item in result["rewrites"])


@pytest.mark.parametrize("duration", [30.0, 90.0, 119.0, 170.3, 600.0])
def test_short_medium_long_video_uses_internal_corrected_asr_without_exposing_transcript(monkeypatch, tmp_path: Path, duration: float):
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
                transcript="完整财经转写内容" * int(duration * 3),
                segments=[ASRSegment(0, duration / 2, "完整财经转写内容" * int(duration * 1.5)), ASRSegment(duration / 2, duration, "完整财经转写内容" * int(duration * 1.5))],
                coverage_seconds=duration,
            ),
        ),
    )
    observed = {}

    async def fake_analyze(*_args, **kwargs):
        observed["raw_script"] = kwargs["raw_script"]
        return _analysis()

    monkeypatch.setattr(viral_pipeline, "analyze_viral_script", fake_analyze)

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
    assert observed["raw_script"].startswith("完整财经转写内容")
    assert "transcript" not in result
    assert "raw_transcript" not in result
    assert "timeline" not in result
    assert "review_segments" not in result
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
    assert partial["ok"] is False
    assert partial["error_code"] == "asr_quality_insufficient"
    assert partial["diagnostic"]["quality_check"] == "coverage"
    assert "transcript" not in partial
    assert "timeline" not in partial

    monkeypatch.setattr(viral_pipeline, "transcribe_audio", lambda *_args: asyncio.sleep(0, result=ASRResult(ok=False, fallback_reason="ASR provider failed")))
    failed = asyncio.run(viral_pipeline._process_video_path(_Supabase(), **kwargs))
    assert failed["ok"] is False
    assert failed["error_code"] == "asr_failed"
    assert failed["fallback_reason"] == "ASR provider failed"


def legacy_fixed_length_long_transcript_uses_every_chunk_and_full_rewrite_is_longer(monkeypatch):
    transcript = "甲" * 5000 + "乙" * 5000 + "丙" * 700
    seen_chunks = []

    async def fake_generate(_self, *, payload, **_kwargs):
        if "transcript_chunk" in payload:
            seen_chunks.append(payload["transcript_chunk"])
            return {"summary": f"段落{payload['part']}摘要：" + payload["transcript_chunk"][:20]}
        full = any("完整版" in item for item in payload["requirements"])
        size = 1000 if full else 300
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
    assert viral_analyzer._cjk_len(full["rewrites"][0]["script"]) >= 900
    assert viral_analyzer._cjk_len(short["rewrites"][0]["script"]) >= 250
    assert viral_analyzer._cjk_len(full["rewrites"][0]["script"]) > viral_analyzer._cjk_len(short["rewrites"][0]["script"]) * 2


def legacy_fixed_length_public_metadata_full_mode_is_downgraded_to_finite_summary(monkeypatch):
    scripts = [
        "这条公开标题能确认的重点有限，因此这里只分析标题里的反差信息。" * 5,
        "从普通用户角度看，公开信息只说明了话题方向，不能代替完整视频观点。" * 5,
        "从行业角度可以关注标题呈现的趋势，但案例和数据仍需原视频验证。" * 5,
    ]

    async def fake_generate(_self, **_kwargs):
        return {
            **_analysis(150),
            "cases": ["模型虚构的历史案例"],
            "data_points": ["模型虚构的资金数据 999 亿"],
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
    assert all(len(item["script"]) >= 60 for item in result["rewrites"])
    assert result["cases"] == []
    assert result["data_points"] == []
    assert result["diagnostics"]["rewrite_length_requested"] == "full"
    assert result["diagnostics"]["rewrite_length_effective"] == "short"


def test_public_metadata_real_110_119_119_outputs_use_evidence_aware_minimum(monkeypatch):
    scripts = ["甲" * 110, "乙" * 119, "丙" * 119]
    observed_payload = {}

    async def fake_generate(_self, *, payload, **_kwargs):
        observed_payload.update(payload)
        return {
            **_analysis(119),
            "cases": [],
            "data_points": [],
            "rewrites": [{"title": f"版本{i}", "script": scripts[i - 1]} for i in range(1, 4)],
        }

    def preserve_real_lengths(payload, *, language):
        assert language == "zh"
        return {
            "topic": payload["topic"],
            "hook": payload["hook"],
            "selling_points": payload["selling_points"],
            "structure": payload["structure"],
            "template": payload["template"],
            "core_points": payload["core_points"],
            "arguments": payload["arguments"],
            "cases": payload["cases"],
            "data_points": payload["data_points"],
            "rewrites": payload["rewrites"],
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", preserve_real_lengths)
    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            source_url="https://example.com/video",
            raw_script="平台：douyin\n标题：中国平安公开信息解读\n简介：仅能确认标题和简介，完整观点、案例及数据均无法确认。",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
            source_scope="public_metadata",
        )
    )

    assert result["diagnostics"]["rewrite_actual_chars"] == [110, 119, 119]
    assert 60 <= result["diagnostics"]["rewrite_target_chars"] < 110
    assert "public_metadata" == observed_payload["source_scope"]
    assert any("不得为凑字数" in item for item in observed_payload["requirements"])


def legacy_fixed_length_full_content_short_output_gets_one_targeted_expansion(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis(100)
        additions = [
            "。".join(f"补充原稿事实甲的论证步骤{i}仍受转写内容约束" for i in range(55)),
            "。".join(f"补充原稿案例乙的条件与结论{i}均保留限定语" for i in range(55)),
            "。".join(f"补充原稿数据丙的意义分析{i}不增加任何新数字" for i in range(55)),
        ]
        return {
            "supplements": [
                {"index": i, "title": f"版本{i + 1}", "additional_script": additions[i]}
                for i in range(3)
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="原稿事实甲、案例乙、数据丙。" * 30,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert len(calls) == 2
    assert all(length >= 900 for length in result["diagnostics"]["rewrite_actual_chars"])
    assert result["diagnostic"]["actual_chars"] == result["diagnostics"]["rewrite_actual_chars"]
    assert result["diagnostic"]["length_unit"] == "cjk_chars"
    assert "corrected_transcript" in calls[1]
    assert "supplements_requested" in calls[1]
    assert "rewrites" not in calls[1]["schema"]
    assert any("主要观点、论据、案例、数据和行动建议" in item for item in calls[1]["requirements"])
    assert all(
        item["script"].startswith(calls[1]["current_rewrites"][index]["script"])
        for index, item in enumerate(result["rewrites"])
    )


def legacy_fixed_length_full_content_uses_second_targeted_round_when_first_round_is_still_short(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([300, 320, 340])
        round_number = payload["supplement_round"]
        addition_length = 400 if round_number == 1 else 260
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": chr(ord("丁") + item["index"]) * addition_length + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写中的观点、论据、案例、数据和行动建议。" * 80,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert len(calls) == 3
    assert calls[1]["supplement_round"] == 1
    assert calls[2]["supplement_round"] == 2
    assert [item["gap_chars"] for item in calls[1]["supplements_requested"]] == [600, 580, 560]
    assert [item["current_chars"] for item in calls[2]["supplements_requested"]] == [700, 720, 740]
    assert result["diagnostic"]["actual_chars"] == [960, 980, 1000]


def legacy_fixed_length_full_content_realistic_model_returns_only_forty_percent(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([500, 520, 540])
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": chr(ord("丁") + item["index"])
                    * round(item["target_additional_chars"] * 0.4)
                    + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写中的观点、条件、案例、风险和行动建议。" * 80,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert len(calls) == 2
    assert any("1100–1300" in item for item in calls[0]["requirements"])
    assert any("因果解释、适用条件、具体例子、风险与误区、可执行建议" in item for item in calls[1]["requirements"])
    assert any("机械重复" in item for item in calls[1]["requirements"])
    assert [item["target_additional_chars"] for item in calls[1]["supplements_requested"]] == [1800, 1800, 1800]
    assert result["diagnostic"]["actual_chars"] == [1220, 1240, 1260]
    assert all(item["script"].endswith("。") for item in result["rewrites"])


def legacy_fixed_length_second_round_uses_observed_low_yield_and_reaches_safe_interval(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([400, 420, 440])
        addition_length = 100 if payload["supplement_round"] == 1 else 650
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": chr(ord("丁") + item["index"]) * addition_length + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写中的观点、条件、案例、风险和行动建议。" * 80,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    second_requests = calls[2]["supplements_requested"]
    assert all(item["planning_yield_rate"] == 0.1 for item in second_requests)
    assert all(item["target_additional_chars"] == 1800 for item in second_requests)
    assert result["diagnostic"]["actual_chars"] == [1150, 1170, 1190]
    assert result["diagnostic"]["length_repair_rounds"][1]["items"][0]["returned_additional_chars"] == 100


def legacy_fixed_length_full_content_899_boundary_targets_safe_final_interval_and_passes(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([950, 980, 899])
        return {
            "supplements": [
                {
                    "index": 2,
                    "title": "版本3",
                    "additional_script": "边" * 121 + "。",
                }
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写。" * 200,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    request = calls[1]["supplements_requested"]
    assert len(calls) == 2
    assert request[0]["index"] == 2
    assert request[0]["current_chars"] == 899
    assert request[0]["gap_chars"] == 1
    assert request[0]["desired_final_chars"] == 1175
    assert request[0]["planning_yield_rate"] == 0.25
    assert request[0]["target_additional_chars"] == 1104
    assert request[0]["maximum_additional_chars"] == 1800
    assert result["diagnostic"]["actual_chars"] == [950, 980, 1020]


def legacy_fixed_length_full_content_only_supplements_the_single_deficient_rewrite(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([930, 700, 1100])
        return {
            "supplements": [
                {"index": 1, "title": "版本2", "additional_script": "补" * 330 + "。"}
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写。" * 200,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert len(calls) == 2
    assert [item["index"] for item in calls[1]["supplements_requested"]] == [1]
    assert result["diagnostic"]["actual_chars"] == [930, 1030, 1100]


def legacy_fixed_length_full_content_keeps_one_qualified_version_and_batches_two_deficient_versions(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([1000, 600, 700])
        return {
            "supplements": [
                {
                    "index": item["index"],
                    "title": item["title"],
                    "additional_script": chr(ord("丁") + item["index"]) * 500 + "。",
                }
                for item in payload["supplements_requested"]
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写。" * 200,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert [item["index"] for item in calls[1]["supplements_requested"]] == [1, 2]
    assert result["diagnostic"]["actual_chars"] == [1000, 1100, 1200]
    assert result["rewrites"][0]["script"] == calls[1]["current_rewrites"][0]["script"]


def legacy_fixed_length_full_content_expansion_still_short_is_structured_failure(monkeypatch):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis(100)
        return {
            "supplements": [
                {"index": item["index"], "title": item["title"], "additional_script": "补充太短。"}
                for item in payload["supplements_requested"]
            ]
        }

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    with pytest.raises(Exception) as raised:
        asyncio.run(
            viral_analyzer.analyze_viral_script(
                _Supabase(),
                user_id="u1",
                email="u@example.com",
                raw_script="完整转写内容。" * 100,
                industry="knowledge",
                language="zh",
                rewrite_length="full",
            )
        )

    detail = raised.value.detail
    assert detail["code"] == "analysis_output_too_short"
    assert detail["stage"] == "rewriting"
    assert detail["retryable"] is False
    assert detail["target_chars"] == 900
    assert detail["maximum_chars"] == 1500
    assert detail["length_unit"] == "cjk_chars"
    assert len(detail["actual_chars"]) == 3
    assert "实际为" in detail["message"]
    assert len(calls) == 1 + viral_analyzer.MAX_REWRITE_SUPPLEMENT_ROUNDS
    assert [call["supplement_round"] for call in calls[1:]] == [1, 2]
    assert [round_["stage"] for round_ in detail["length_repair_rounds"]] == ["initial", "expanding", "expanding"]
    assert detail["length_repair_rounds"][-1]["actual_chars"] == detail["actual_chars"]
    assert all(
        after >= before
        for before, after in zip(
            detail["length_repair_rounds"][0]["actual_chars"],
            detail["length_repair_rounds"][-1]["actual_chars"],
            strict=True,
        )
    )
    assert detail["resource_limits"]["maximum_supplement_rounds"] == 2
    assert detail["resource_limits"]["maximum_requested_additional_chars"] == 1800


def test_overlong_rewrite_converges_at_complete_sentence_boundary():
    script = ("甲" * 700 + "。") + ("乙" * 700 + "。") + ("丙" * 300 + "。")

    trimmed = viral_analyzer._trim_to_sentence_boundary(
        script,
        minimum_chars=900,
        maximum_chars=1500,
    )

    assert trimmed.endswith("。")
    assert viral_analyzer._cjk_len(trimmed) == 1400
    assert "丙" not in trimmed


def legacy_fixed_length_overlong_initial_rewrites_are_trimmed_without_supplement_call(monkeypatch):
    calls = []
    overlong = ("甲" * 700 + "。") + ("乙" * 700 + "。") + ("丙" * 300 + "。")

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        result = _analysis()
        result["rewrites"] = [
            {"title": f"版本{index + 1}", "script": overlong.replace("甲", chr(ord("甲") + index))}
            for index in range(3)
        ]
        return result

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    result = asyncio.run(
        viral_analyzer.analyze_viral_script(
            _Supabase(),
            user_id="u1",
            email="u@example.com",
            raw_script="完整转写。" * 200,
            industry="knowledge",
            language="zh",
            rewrite_length="full",
        )
    )

    assert len(calls) == 1
    assert result["diagnostic"]["actual_chars"] == [1400, 1400, 1400]
    assert all(item["script"].endswith("。") for item in result["rewrites"])
    assert result["diagnostic"]["length_repair_rounds"][-1]["stage"] == "sentence_boundary_trim"


@pytest.mark.parametrize(
    "expansion",
    [
        {"supplements": [{"index": 0, "title": "版本1", "additional_script": ""}]},
        {},
        {"supplements": [{"title": "缺少index", "additional_script": "补" * 500}]},
    ],
)
def legacy_fixed_length_empty_or_missing_supplement_fields_end_in_structured_failure(monkeypatch, expansion):
    calls = []

    async def fake_generate(_self, *, payload, **_kwargs):
        calls.append(payload)
        if "supplements_requested" not in payload:
            return _analysis_with_lengths([600, 620, 640])
        return expansion

    monkeypatch.setattr(viral_analyzer, "_assert_viral_quota", lambda *_args, **_kwargs: {"plan": "pro", "used": 0, "monthly_limit": 99})
    monkeypatch.setattr(viral_analyzer.LLMProvider, "generate_json", fake_generate)
    monkeypatch.setattr(viral_analyzer, "validate_viral_analysis_payload", _preserve_analysis_lengths)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            viral_analyzer.analyze_viral_script(
                _Supabase(),
                user_id="u1",
                email="u@example.com",
                raw_script="完整转写。" * 200,
                industry="knowledge",
                language="zh",
                rewrite_length="full",
            )
        )

    detail = raised.value.detail
    assert detail["code"] == "analysis_output_too_short"
    assert detail["actual_chars"] == [600, 620, 640]
    assert len(detail["length_repair_rounds"]) == 3
    assert all(
        item["returned_additional_chars"] == 0
        for round_ in detail["length_repair_rounds"][1:]
        for item in round_["items"]
    )
    assert len(calls) == 3


def test_rewrite_length_failure_preserves_actual_chars_in_pipeline_payload():
    error = HTTPException(
        status_code=502,
        detail={
            "code": "analysis_output_too_short",
            "stage": "rewriting",
            "message": "AI 改写长度未达到 900–1500 个中文字符；实际为 731 / 601 / 495。",
            "retryable": False,
            "target_chars": 900,
            "maximum_chars": 1500,
            "actual_chars": [731, 601, 495],
        },
    )

    result = viral_pipeline._analysis_error_result(error, metadata={}, source_type="uploaded_video_asr")

    assert result["error_code"] == "analysis_output_too_short"
    assert result["diagnostic"]["target_chars"] == 900
    assert result["diagnostic"]["maximum_chars"] == 1500
    assert result["diagnostic"]["actual_chars"] == [731, 601, 495]
    assert "731 / 601 / 495" in result["fallback_reason"]


def test_manual_text_entry_binds_and_returns_structured_request_id(monkeypatch, caplog):
    observed = {}

    async def fake_analyze(*_args, **_kwargs):
        observed["request_id"] = viral_diagnostics.current_request_id()
        return {
            **_analysis(1000),
            "diagnostic": {
                "actual_chars": [902, 1068, 1111],
                "target_chars": 900,
                "maximum_chars": 1500,
                "length_unit": "cjk_chars",
            },
        }

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    caplog.set_level("INFO", logger="app.api.viral")

    result = asyncio.run(
        viral_api.analyze_viral(
            payload=viral_api.ViralAnalyzeRequest(
                raw_script="完整财经文本",
                industry="knowledge",
                language="zh",
                rewrite_length="full",
            ),
            token="token",
            supabase=_Supabase(),
        )
    )

    assert re.fullmatch(r"viral_[0-9a-f]{16}", observed["request_id"])
    assert result["request_id"] == observed["request_id"]
    assert result["diagnostic"]["actual_chars"] == [902, 1068, 1111]
    assert f"request_id={result['request_id']}" in caplog.text
    assert "actual_chars=[902, 1068, 1111]" in caplog.text
    assert viral_diagnostics.current_request_id() == ""


def test_manual_text_same_submission_concurrently_calls_analyzer_once(monkeypatch):
    viral_analysis_idempotency.clear()
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_analyze(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {
            **_analysis(1000),
            "diagnostic": {
                "actual_chars": [902, 1068, 1111],
                "target_chars": 900,
                "maximum_chars": 1500,
                "length_unit": "cjk_chars",
            },
        }

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    payload = viral_api.ViralAnalyzeRequest(
        raw_script="完整财经文本",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        client_submission_id="viral_submission_0123456789abcdef0123456789abcdef",
    )

    async def run():
        first = asyncio.create_task(viral_api.analyze_viral(payload=payload, token="token", supabase=_Supabase()))
        await started.wait()
        second = asyncio.create_task(viral_api.analyze_viral(payload=payload, token="token", supabase=_Supabase()))
        await asyncio.sleep(0)
        release.set()
        return await asyncio.gather(first, second)

    first_result, second_result = asyncio.run(run())
    assert calls == 1
    assert first_result == second_result
    assert first_result["request_id"] == second_result["request_id"]
    assert first_result["client_submission_id"] == payload.client_submission_id


def test_manual_text_completed_submission_reuses_success_without_analyzer(monkeypatch):
    viral_analysis_idempotency.clear()
    calls = 0

    async def fake_analyze(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {
            **_analysis(1000),
            "diagnostic": {
                "actual_chars": [930, 940, 950],
                "target_chars": 900,
                "maximum_chars": 1500,
                "length_unit": "cjk_chars",
            },
        }

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    payload = viral_api.ViralAnalyzeRequest(
        raw_script="同一输入",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        client_submission_id="viral_submission_11111111111111111111111111111111",
    )

    first = asyncio.run(viral_api.analyze_viral(payload=payload, token="token", supabase=_Supabase()))
    second = asyncio.run(viral_api.analyze_viral(payload=payload, token="token", supabase=_Supabase()))
    assert calls == 1
    assert second == first


def test_manual_text_failed_submission_reuses_first_failure(monkeypatch):
    viral_analysis_idempotency.clear()
    calls = 0

    async def fake_analyze(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise HTTPException(
            status_code=502,
            detail={
                "code": "analysis_output_too_short",
                "stage": "rewriting",
                "message": "长度不足。",
                "retryable": False,
                "actual_chars": [899, 930, 940],
            },
        )

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    payload = viral_api.ViralAnalyzeRequest(
        raw_script="失败输入",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        client_submission_id="viral_submission_22222222222222222222222222222222",
    )

    failures = []
    for _ in range(2):
        with pytest.raises(HTTPException) as raised:
            asyncio.run(viral_api.analyze_viral(payload=payload, token="token", supabase=_Supabase()))
        failures.append((raised.value.status_code, raised.value.detail))

    assert calls == 1
    assert failures[0] == failures[1]
    assert failures[0][1]["request_id"].startswith("viral_")
    assert failures[0][1]["client_submission_id"] == payload.client_submission_id


def test_manual_text_changed_input_with_new_submission_runs_again(monkeypatch):
    viral_analysis_idempotency.clear()
    calls = 0

    async def fake_analyze(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {**_analysis(1000), "diagnostic": {"actual_chars": [910, 920, 930]}}

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    first_payload = viral_api.ViralAnalyzeRequest(
        raw_script="输入一",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        client_submission_id="viral_submission_33333333333333333333333333333333",
    )
    second_payload = viral_api.ViralAnalyzeRequest(
        raw_script="输入二",
        industry="knowledge",
        language="zh",
        rewrite_length="full",
        client_submission_id="viral_submission_44444444444444444444444444444444",
    )

    asyncio.run(viral_api.analyze_viral(payload=first_payload, token="token", supabase=_Supabase()))
    asyncio.run(viral_api.analyze_viral(payload=second_payload, token="token", supabase=_Supabase()))
    assert calls == 2


def test_idempotency_store_threaded_claim_has_exactly_one_owner():
    store = InMemoryIdempotencyStore()

    def claim():
        return store.claim(user_id="u1", submission_id="submission", fingerprint="fingerprint")

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(lambda _index: claim(), range(32)))

    assert sum(item.is_owner for item in claims) == 1
    assert len({id(item.future) for item in claims}) == 1


def test_manual_text_rejects_reused_submission_id_for_different_input(monkeypatch):
    viral_analysis_idempotency.clear()

    async def fake_analyze(*_args, **_kwargs):
        return {**_analysis(1000), "diagnostic": {"actual_chars": [910, 920, 930]}}

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "analyze_viral_script", fake_analyze)
    submission_id = "viral_submission_55555555555555555555555555555555"
    first_payload = viral_api.ViralAnalyzeRequest(
        raw_script="输入一",
        industry="knowledge",
        client_submission_id=submission_id,
    )
    conflicting_payload = viral_api.ViralAnalyzeRequest(
        raw_script="输入二",
        industry="knowledge",
        client_submission_id=submission_id,
    )
    asyncio.run(viral_api.analyze_viral(payload=first_payload, token="token", supabase=_Supabase()))

    with pytest.raises(HTTPException) as raised:
        asyncio.run(viral_api.analyze_viral(payload=conflicting_payload, token="token", supabase=_Supabase()))

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "idempotency_conflict"


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


def test_frontend_review_player_and_confirmation_flow_are_removed():
    source = (Path(__file__).parents[2] / "web" / "components" / "ViralAnalyzerClient.tsx").read_text(encoding="utf-8")

    assert "SegmentAudioPlayer" not in source
    assert "reviewDrafts" not in source
    assert "确认此段" not in source
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
    assert "client_timeout" in api_source and "request_aborted" in api_source
    assert 'method: "OPTIONS"' not in api_source
    assert "cors_preflight_failed" not in api_source
    assert "cors_or_api_unreachable" in api_source
    assert "api_unauthorized" in api_source and "upload_too_large" in api_source and "api_server_error" in api_source
    assert "const CLIENT_API_URL" in api_source
    assert "process.env.SERVER_API_URL || CLIENT_API_URL" in api_source
    assert "request_id: unavailable" in api_source
    assert "retryable: true" in api_source
    assert "endpoint:" in api_source
    assert 'setRequestHeader("Content-Type"' not in api_source
    assert "上传进度：" in component_source
    assert "文件大小：" in component_source
    assert "仅基于公开信息（非完整拆解）" in component_source
    assert "无法精确匹配原视频时长" in component_source
    assert "公开信息摘要（无法精确匹配原视频时长）" in component_source
    assert "hasCompleteUserInput" in component_source
    assert "setFullRewriteAvailable(true);" in component_source
    assert "ASR 模型不可用" in component_source
    assert "AI 响应格式错误" in component_source
    assert "请求 ID：" in component_source
    assert "匹配原视频时长（推荐，原文约 90%–110%）" in component_source
    assert "精简版（原文约 65%–80%）" in component_source
    assert "适度扩展（原文约 110%–130%）" in component_source
    assert "约 900–1500 中文字符" not in component_source
    assert "实际中文字数：" in component_source
    assert "result.request_id" in component_source
    assert "result?.diagnostic?.actual_chars" in component_source
    assert 'actual_chars: payload.diagnostics.rewrite_actual_chars' in component_source
    assert "自动转写稿（AI校正，建议人工复核）" not in component_source
    assert "查看原始ASR转写" not in component_source
    assert "确认此段" not in component_source
    assert "全部确认后继续拆解" not in component_source
    assert "SegmentAudioPlayer" not in component_source
    assert "continueReviewedViralPipeline" not in component_source
    assert "setUploadProgress(null)" in component_source


def test_frontend_analysis_submission_has_synchronous_duplicate_gate_and_loading_state():
    component_source = (Path(__file__).parents[2] / "web" / "components" / "ViralAnalyzerClient.tsx").read_text(encoding="utf-8")
    handler = component_source[component_source.index("async function handleAnalyze()") : component_source.index("async function copyScript")]

    assert "const analysisInFlightRef = useRef(false);" in component_source
    assert "if (analysisInFlightRef.current) return;" in handler
    assert "analysisInFlightRef.current = true;" in handler
    assert handler.index("analysisInFlightRef.current = true;") < handler.index("setLoading(true);")
    assert "analysisInFlightRef.current = false;" in handler
    assert handler.index("analysisInFlightRef.current = false;") < handler.index("setLoading(false);")
    assert "disabled={loading || checking}" in component_source
    assert "{loading ? loadingLabel() : t.start}" in component_source
    assert "manualSubmissionFingerprint" in component_source
    assert "client_submission_id: submissionId" in component_source
    assert 'status === "succeeded"' in handler
    assert 'status === "failed"' in handler
    assert handler.count("analyzeViralScript(") == 1
    assert "manualSubmissionRef.current = null;" in component_source
    for field in ("source_url", "raw_script", "industry", "language", "rewrite_length"):
        assert field in component_source[component_source.index("async function manualSubmissionFingerprint") : component_source.index("function newClientSubmissionId")]


def test_review_continuation_endpoint_and_public_payload_are_removed():
    paths = {route.path for route in viral_api.router.routes}
    assert "/pipeline/continue" not in paths


def test_real_multipart_12_7mb_route_and_cors(monkeypatch):
    observed = {}
    preview_origin = "https://kaiqiang-ai-git-p237-long-video-d-eedb85-kaiqiang-ai-s-projects.vercel.app"

    async def fake_pipeline(_supabase, **kwargs):
        observed["filename"] = kwargs["upload"].filename
        observed["size"] = len(await kwargs["upload"].read())
        return {"ok": True, "source_type": "uploaded_video_asr"}

    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})
    monkeypatch.setattr(viral_api, "run_uploaded_viral_pipeline", fake_pipeline)
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[preview_origin],
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
            "Origin": preview_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == preview_origin
    assert "POST" in preflight.headers["access-control-allow-methods"]
    allowed_headers = preflight.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers

    plain_options = client.options(
        "/api/viral/pipeline/upload",
        headers={"Origin": preview_origin},
    )
    assert plain_options.status_code == 204
    assert plain_options.headers["access-control-allow-origin"] == preview_origin

    payload = b"x" * 13_299_712
    response = client.post(
        "/api/viral/pipeline/upload",
        headers={"Origin": preview_origin, "Authorization": "Bearer token"},
        files={"video_file": ("170-seconds.mp4", payload, "video/mp4")},
        data={"industry": "knowledge", "language": "zh", "rewrite_length": "full"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == preview_origin
    assert observed == {"filename": "170-seconds.mp4", "size": len(payload)}


def test_upload_returns_busy_without_starting_second_asr(monkeypatch):
    class _BusyLock:
        def locked(self):
            return True

    monkeypatch.setattr(viral_api, "_viral_upload_lock", _BusyLock())
    monkeypatch.setattr(viral_api, "get_authenticated_user", lambda *_args: {"id": "u1", "email": "u@example.com"})

    result = asyncio.run(
        viral_api.run_uploaded_viral_agent_pipeline(
            video_file=SimpleNamespace(filename="busy.mp4"),
            source_url="",
            industry="knowledge",
            language="zh",
            rewrite_length="full",
            token="token",
            supabase=_Supabase(),
        )
    )

    assert result["ok"] is False
    assert result["code"] == "asr_busy"
    assert result["stage"] == "uploading"
    assert result["retryable"] is True
