from app.services.avatar_video_quality import VideoQualityMetrics, evaluate_video_quality_metadata


def _codes(result):
    return {reason.code for reason in result.reasons}


def test_recommended_mp4_is_grade_a():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=12.3, width=1080, height=1920, fps=30, codec="h264", format="mov,mp4,m4a,3gp,3g2,mj2"),
        file_extension=".mp4",
    )

    assert result.grade == "A"
    assert result.success is True
    assert result.reasons == []


def test_short_video_is_blocked():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=7.9, width=720, height=1280, fps=30, codec="h264", format="mov,mp4"),
        file_extension=".mp4",
    )

    assert result.grade == "C"
    assert "video_too_short" in _codes(result)


def test_long_video_is_blocked():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=60.1, width=720, height=1280, fps=30, codec="h264", format="mov,mp4"),
        file_extension=".mp4",
    )

    assert result.grade == "C"
    assert "video_too_long" in _codes(result)


def test_low_resolution_is_blocked():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=12, width=480, height=854, fps=30, codec="h264", format="mov,mp4"),
        file_extension=".mp4",
    )

    assert result.grade == "C"
    assert "low_resolution" in _codes(result)


def test_unsupported_format_is_blocked():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=12, width=720, height=1280, fps=30, codec="h264", format="avi"),
        file_extension=".avi",
    )

    assert result.grade == "C"
    assert "unsupported_format" in _codes(result)


def test_edge_duration_is_warning_grade_b():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=8.5, width=720, height=1280, fps=30, codec="h264", format="mov,mp4"),
        file_extension=".mp4",
    )

    assert result.grade == "B"
    assert "duration_suboptimal" in _codes(result)


def test_unusual_fps_is_warning_grade_b():
    result = evaluate_video_quality_metadata(
        VideoQualityMetrics(duration_seconds=12, width=720, height=1280, fps=15, codec="h264", format="mov,mp4"),
        file_extension=".mp4",
    )

    assert result.grade == "B"
    assert "fps_unusual" in _codes(result)


def test_missing_video_stream_is_blocked():
    result = evaluate_video_quality_metadata(VideoQualityMetrics(duration_seconds=12, format="mov,mp4"), file_extension=".mp4")

    assert result.grade == "C"
    assert "invalid_video_stream" in _codes(result)
