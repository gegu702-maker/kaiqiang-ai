import re


def build_script_webvtt(script: str) -> bytes:
    chunks = _split_script(script)
    lines = ["WEBVTT", ""]

    for index, chunk in enumerate(chunks):
        start_seconds = index * 4
        end_seconds = start_seconds + 4
        lines.extend(
            [
                f"{_format_timestamp(start_seconds)} --> {_format_timestamp(end_seconds)}",
                chunk,
                "",
            ]
        )

    return "\n".join(lines).encode("utf-8")


def _split_script(script: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", script.strip())
    if not normalized:
        return [" "]

    sentences = [part.strip() for part in re.split(r"(?<=[。！？.!?])\s*", normalized) if part.strip()]
    chunks: list[str] = []

    for sentence in sentences:
        while len(sentence) > 42:
            chunks.append(sentence[:42])
            sentence = sentence[42:]
        if sentence:
            chunks.append(sentence)

    return chunks or [normalized[:42]]


def _format_timestamp(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.000"
