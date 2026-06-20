from app.services import musetalk_client
from app.services.subtitles import SubtitleBurnError, SubtitleSegment


def test_optional_subtitles_reports_disabled_when_feature_off(monkeypatch):
    monkeypatch.setattr(musetalk_client.settings, "avatar_subtitles_enabled", False)

    content, status = musetalk_client._with_optional_subtitles(
        b"original-video",
        task_id="task-1",
        script_text="hello",
    )

    assert content == b"original-video"
    assert status == "disabled"


def test_optional_subtitles_reports_disabled_for_empty_script(monkeypatch):
    monkeypatch.setattr(musetalk_client.settings, "avatar_subtitles_enabled", True)

    content, status = musetalk_client._with_optional_subtitles(
        b"original-video",
        task_id="task-2",
        script_text=" ",
    )

    assert content == b"original-video"
    assert status == "disabled"


def test_optional_subtitles_falls_back_to_original_on_burn_error(monkeypatch):
    monkeypatch.setattr(musetalk_client.settings, "avatar_subtitles_enabled", True)
    monkeypatch.setattr(musetalk_client.settings, "avatar_subtitle_fallback_on_error", True)
    monkeypatch.setattr(musetalk_client, "probe_video_duration", lambda *_args, **_kwargs: 2.0)
    monkeypatch.setattr(
        musetalk_client,
        "build_subtitle_segments",
        lambda *_args, **_kwargs: [SubtitleSegment(start=0, end=2, lines=["hello"])],
    )
    monkeypatch.setattr(musetalk_client, "write_ass_file", lambda *_args, **_kwargs: None)

    def fail_burn(*_args, **_kwargs):
        raise SubtitleBurnError("burn failed", {"returncode": 1})

    monkeypatch.setattr(musetalk_client, "burn_subtitles_to_video", fail_burn)

    content, status = musetalk_client._with_optional_subtitles(
        b"original-video",
        task_id="task-3",
        script_text="hello",
    )

    assert content == b"original-video"
    assert status == "fallback_original"
