from __future__ import annotations

from enum import Enum


class VideoAgentStep(str, Enum):
    analyze_product = "analyze_product"
    generate_titles = "generate_titles"
    generate_script = "generate_script"
    generate_storyboard = "generate_storyboard"
    generate_visual_prompts = "generate_visual_prompts"
    generate_avatar_video = "generate_avatar_video"
    edit_video = "edit_video"
    compose_subtitles = "compose_subtitles"
    export_video = "export_video"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


VIDEO_AGENT_PIPELINE = [
    VideoAgentStep.analyze_product,
    VideoAgentStep.generate_titles,
    VideoAgentStep.generate_script,
    VideoAgentStep.generate_storyboard,
    VideoAgentStep.generate_visual_prompts,
    VideoAgentStep.generate_avatar_video,
    VideoAgentStep.edit_video,
    VideoAgentStep.compose_subtitles,
    VideoAgentStep.export_video,
]


def initial_pipeline_state() -> list[dict[str, str]]:
    return [{"step": step.value, "status": StepStatus.pending.value} for step in VIDEO_AGENT_PIPELINE]
