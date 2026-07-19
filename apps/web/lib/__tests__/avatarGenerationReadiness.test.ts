import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTemplateGenerateRequest,
  deriveAvatarGenerationCapabilities,
  getAvatarGenerationAction,
  getAvatarGenerationButtonLabelKey,
  parsePreviewTtsReadyResponse,
} from "../avatarGenerationReadiness";

const previewReady = deriveAvatarGenerationCapabilities({
  previewEnvironment: true,
  responseOk: true,
  videoGenerationStatus: "disabled",
  previewTtsOnlyStatus: "ready",
});

test("Preview video disabled does not disable a ready TTS-only action", () => {
  assert.deepEqual(previewReady, {
    previewSafeMode: true,
    previewTtsOnlyReady: true,
    videoGenerationReady: false,
  });
  assert.deepEqual(
    getAvatarGenerationAction({
      capabilities: previewReady,
      isGenerating: false,
      hasText: true,
      hasTemplate: true,
      hasVoice: true,
      hasVideoFile: false,
      hasAudioFile: false,
    }),
    { mode: "preview_tts", enabled: true },
  );
});

test("Preview TTS-only stays disabled when provider readiness is unavailable", () => {
  const capabilities = deriveAvatarGenerationCapabilities({
    previewEnvironment: true,
    responseOk: true,
    videoGenerationStatus: "disabled",
    previewTtsOnlyStatus: "unavailable",
  });
  assert.equal(
    getAvatarGenerationAction({
      capabilities,
      isGenerating: false,
      hasText: true,
      hasTemplate: true,
      hasVoice: true,
      hasVideoFile: false,
      hasAudioFile: false,
    }).enabled,
    false,
  );
});

test("button labels distinguish Preview TTS-only from video generation", () => {
  const previewAction = { mode: "preview_tts" as const, enabled: true };
  const videoAction = { mode: "video" as const, enabled: true };
  assert.equal(
    getAvatarGenerationButtonLabelKey({ action: previewAction, isGenerating: false, healthChecking: false, healthUnavailable: false }),
    "generate_preview_tts",
  );
  assert.equal(
    getAvatarGenerationButtonLabelKey({ action: previewAction, isGenerating: true, healthChecking: false, healthUnavailable: false }),
    "generating_preview_tts",
  );
  assert.equal(
    getAvatarGenerationButtonLabelKey({ action: previewAction, isGenerating: false, healthChecking: false, healthUnavailable: true }),
    "preview_tts_unavailable",
  );
  assert.equal(
    getAvatarGenerationButtonLabelKey({ action: videoAction, isGenerating: false, healthChecking: false, healthUnavailable: false }),
    "generate_video",
  );
});

test("Preview TTS-only requires text and blocks existing media inputs", () => {
  const base = {
    capabilities: previewReady,
    isGenerating: false,
    hasTemplate: true,
    hasVoice: true,
  };
  assert.equal(getAvatarGenerationAction({ ...base, hasText: false, hasVideoFile: false, hasAudioFile: false }).enabled, false);
  assert.equal(getAvatarGenerationAction({ ...base, hasText: true, hasVideoFile: true, hasAudioFile: false }).enabled, false);
  assert.equal(getAvatarGenerationAction({ ...base, hasText: true, hasVideoFile: false, hasAudioFile: true }).enabled, false);
});

test("non-Preview keeps the existing video readiness behavior", () => {
  const ready = deriveAvatarGenerationCapabilities({
    previewEnvironment: false,
    responseOk: true,
    musetalkStatus: "ready",
  });
  const unavailable = deriveAvatarGenerationCapabilities({
    previewEnvironment: false,
    responseOk: true,
    musetalkStatus: "unavailable",
  });
  const input = {
    isGenerating: false,
    hasText: false,
    hasTemplate: true,
    hasVoice: true,
    hasVideoFile: false,
    hasAudioFile: false,
  };

  assert.deepEqual(getAvatarGenerationAction({ ...input, capabilities: ready }), { mode: "video", enabled: true });
  assert.deepEqual(getAvatarGenerationAction({ ...input, capabilities: unavailable }), { mode: "video", enabled: false });
});

test("template request contains text, template, and public voice without media inputs", () => {
  const request = buildTemplateGenerateRequest({
    avatarTemplateId: "business_female_01",
    scriptText: "  Preview TTS  ",
    language: "zh-CN",
    voice: "zh_female_default",
    speedRatio: 1,
  });

  assert.deepEqual(request, {
    avatar_template_id: "business_female_01",
    script_text: "Preview TTS",
    language: "zh-CN",
    voice: "zh_female_default",
    speed_ratio: 1,
  });
  assert.equal("audio_url" in request, false);
  assert.equal("video_file" in request, false);
});

test("tts_ready is accepted only as an audio result without a task", () => {
  assert.deepEqual(
    parsePreviewTtsReadyResponse({
      preview_safe_mode: true,
      status: "tts_ready",
      audio_url: "https://preview.example/voice.mp3",
      voice: "zh_female_default",
      task_id: null,
    }),
    {
      audioUrl: "https://preview.example/voice.mp3",
      voice: "zh_female_default",
    },
  );
  assert.equal(
    parsePreviewTtsReadyResponse({
      preview_safe_mode: true,
      status: "tts_ready",
      audio_url: "https://preview.example/voice.mp3",
      task_id: "unexpected-task",
    }),
    null,
  );
});
