from __future__ import annotations

from dataclasses import asdict, dataclass


LENGTH_MODE_RATIOS: dict[str, tuple[float, float]] = {
    "match_source": (0.90, 1.10),
    "concise": (0.65, 0.80),
    "moderate_expand": (1.10, 1.30),
}
LEGACY_LENGTH_MODES = {
    "short": "concise",
    "medium": "match_source",
    "full": "match_source",
}

# Very short inputs still need enough room for a complete spoken paragraph.
# Long inputs are capped so one synchronous LLM response remains bounded.
MIN_DYNAMIC_TARGET_CJK = 60
MAX_DYNAMIC_TARGET_CJK = 1500
MAX_DYNAMIC_CENTER_CJK = 1350
MAX_DYNAMIC_MIN_CJK = 1200


@dataclass(frozen=True)
class RewriteLengthTarget:
    source_cjk: int
    effective_speech_seconds: float | None
    source_density: float | None
    target_min_chars: int
    target_center_chars: int
    target_max_chars: int
    length_mode: str
    exact_duration_match: bool

    def diagnostics(self) -> dict[str, int | float | str | bool | None]:
        return asdict(self)


def normalize_length_mode(value: str) -> str:
    normalized = LEGACY_LENGTH_MODES.get(value, value)
    if normalized not in LENGTH_MODE_RATIOS:
        raise ValueError("Invalid rewrite length mode.")
    return normalized


def calculate_rewrite_length_target(
    *,
    source_cjk: int,
    length_mode: str,
    effective_speech_seconds: float | None = None,
) -> RewriteLengthTarget:
    mode = normalize_length_mode(length_mode)
    source = max(0, int(source_cjk))
    low_ratio, high_ratio = LENGTH_MODE_RATIOS[mode]

    raw_minimum = round(source * low_ratio)
    raw_center = source if mode == "match_source" else round(source * ((low_ratio + high_ratio) / 2))
    raw_maximum = round(source * high_ratio)

    if source < MIN_DYNAMIC_TARGET_CJK:
        minimum = max(40, raw_minimum)
        center = max(MIN_DYNAMIC_TARGET_CJK, raw_center)
        maximum = max(80, raw_maximum, center)
    else:
        minimum = raw_minimum
        center = raw_center
        maximum = raw_maximum

    if maximum > MAX_DYNAMIC_TARGET_CJK:
        minimum = min(minimum, MAX_DYNAMIC_MIN_CJK)
        center = min(max(center, minimum), MAX_DYNAMIC_CENTER_CJK)
        maximum = MAX_DYNAMIC_TARGET_CJK

    seconds = (
        round(float(effective_speech_seconds), 3)
        if effective_speech_seconds is not None and effective_speech_seconds > 0
        else None
    )
    density = round(source / seconds, 3) if seconds else None
    return RewriteLengthTarget(
        source_cjk=source,
        effective_speech_seconds=seconds,
        source_density=density,
        target_min_chars=minimum,
        target_center_chars=center,
        target_max_chars=maximum,
        length_mode=mode,
        exact_duration_match=True,
    )


def calculate_public_metadata_target(*, evidence_cjk: int) -> RewriteLengthTarget:
    evidence = max(0, int(evidence_cjk))
    minimum = max(60, min(100, round(evidence * 0.75)))
    maximum = min(240, max(minimum + 40, minimum * 2))
    return RewriteLengthTarget(
        source_cjk=evidence,
        effective_speech_seconds=None,
        source_density=None,
        target_min_chars=minimum,
        target_center_chars=round((minimum + maximum) / 2),
        target_max_chars=maximum,
        length_mode="public_metadata_fallback",
        exact_duration_match=False,
    )
