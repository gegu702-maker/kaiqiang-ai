import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTemplateGenerateRequest,
  deriveAvatarGenerationCapabilities,
  getAvatarGenerationAction,
  getAvatarGenerationButtonLabelKey,
  parsePreviewTtsReadyResponse,
} from "../avatarGenerationReadiness";
import { avatarVoiceGroups, avatarVoiceOptions, DEFAULT_AVATAR_VOICE_KEY, getAvatarVoiceLanguage, getAvatarVoicePreviewAudioPath } from "../avatarVoiceOptions";

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

test("voice options expose 14 internal keys grouped by language while preserving the female default", () => {
  assert.equal(avatarVoiceOptions.length, 14);
  assert.deepEqual(avatarVoiceGroups.map(({ key }) => key), ["zh", "en", "ja"]);
  assert.equal(new Set(avatarVoiceOptions.map(({ key }) => key)).size, 14);
  assert.deepEqual(
    avatarVoiceOptions.reduce<Record<string, number>>((counts, option) => ({ ...counts, [option.group]: (counts[option.group] ?? 0) + 1 }), {}),
    { zh: 10, en: 2, ja: 2 },
  );
  assert.deepEqual(
    Object.fromEntries(
      avatarVoiceOptions
        .filter(({ group }) => group !== "zh")
        .map(({ key, name }) => [key, name.zh]),
    ),
    {
      en_energetic_male_jackson: "活力男声-Jackson（英语）",
      en_energetic_female_ariana: "活力女声-Ariana（英语）",
      ja_male: "日语男声（日语）",
      ja_elegant_female: "气质女生（日语）",
    },
  );
  assert.equal(getAvatarVoiceLanguage("en_energetic_male_jackson"), "en-US");
  assert.equal(getAvatarVoiceLanguage("ja_elegant_female"), "ja-JP");
  assert.equal(DEFAULT_AVATAR_VOICE_KEY, "zh_female_default");
});

test("voice preview audio paths are static public MP3 files keyed by internal voice key", () => {
  for (const option of avatarVoiceOptions) {
    const audioPath = getAvatarVoicePreviewAudioPath(option.key);
    assert.equal(audioPath, `/audio/voice-previews/${option.key}.mp3`);
    assert.equal(audioPath.includes("BV"), false);
    assert.equal(audioPath.startsWith("http"), false);
  }
});

test("all 12 new choices submit internal keys with their matching language", () => {
  for (const option of avatarVoiceOptions.filter(({ key }) => !["zh_female_default", "zh_male_default"].includes(key))) {
    const request = buildTemplateGenerateRequest({
      avatarTemplateId: "business_female_01",
      scriptText: "voice test",
      language: getAvatarVoiceLanguage(option.key),
      voice: option.key,
      speedRatio: 1,
    });
    assert.equal(request.voice, option.key);
    assert.equal(request.language, option.language);
    assert.equal(JSON.stringify(request).includes("BV"), false);
  }
});

test("male selection submits only the internal voice key", () => {
  const request = buildTemplateGenerateRequest({
    avatarTemplateId: "business_male_01",
    scriptText: "Preview male TTS",
    language: "zh-CN",
    voice: "zh_male_default",
    speedRatio: 1,
  });

  assert.equal(request.voice, "zh_male_default");
  assert.equal(JSON.stringify(request).includes("BV002_streaming"), false);
  assert.equal("voice_type" in request, false);
  assert.equal("audio_url" in request, false);
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
