export type AvatarGenerationCapabilities = {
  previewSafeMode: boolean;
  previewTtsOnlyReady: boolean;
  videoGenerationReady: boolean;
};

type HealthCapabilitiesInput = {
  previewEnvironment: boolean;
  responseOk: boolean;
  musetalkStatus?: string;
  videoGenerationStatus?: string;
  previewTtsOnlyStatus?: string;
};

type GenerationActionInput = {
  capabilities: AvatarGenerationCapabilities;
  isGenerating: boolean;
  hasText: boolean;
  hasTemplate: boolean;
  hasVoice: boolean;
  hasVideoFile: boolean;
  hasAudioFile: boolean;
};

export type AvatarGenerationAction = {
  enabled: boolean;
  mode: "preview_tts" | "video";
};

export type AvatarGenerationButtonLabelKey =
  | "generate_video"
  | "generate_preview_tts"
  | "generating_video"
  | "generating_preview_tts"
  | "health_checking"
  | "video_unavailable"
  | "preview_tts_unavailable";

type TemplateGenerateRequestInput = {
  avatarTemplateId: string;
  scriptText: string;
  language: string;
  voice: string;
  speedRatio: number;
};

export type PreviewTtsReadyResult = {
  audioUrl: string;
  voice?: string;
};

const READY_STATUSES = new Set(["ok", "ready", "healthy", "success"]);

function normalizeStatus(status?: string): string {
  return String(status ?? "").trim().toLowerCase();
}

export function deriveAvatarGenerationCapabilities({
  previewEnvironment,
  responseOk,
  musetalkStatus,
  videoGenerationStatus,
  previewTtsOnlyStatus,
}: HealthCapabilitiesInput): AvatarGenerationCapabilities {
  const videoStatus = normalizeStatus(videoGenerationStatus);
  const previewTtsStatus = normalizeStatus(previewTtsOnlyStatus);
  const previewSafeMode =
    previewEnvironment &&
    videoStatus === "disabled" &&
    Boolean(previewTtsStatus);

  return {
    previewSafeMode,
    previewTtsOnlyReady:
      responseOk && previewSafeMode && READY_STATUSES.has(previewTtsStatus),
    videoGenerationReady:
      responseOk && READY_STATUSES.has(normalizeStatus(musetalkStatus)),
  };
}

export function getAvatarGenerationAction({
  capabilities,
  isGenerating,
  hasText,
  hasTemplate,
  hasVoice,
  hasVideoFile,
  hasAudioFile,
}: GenerationActionInput): AvatarGenerationAction {
  if (capabilities.previewSafeMode) {
    return {
      mode: "preview_tts",
      enabled:
        !isGenerating &&
        capabilities.previewTtsOnlyReady &&
        hasText &&
        hasTemplate &&
        hasVoice &&
        !hasVideoFile &&
        !hasAudioFile,
    };
  }

  return {
    mode: "video",
    enabled: !isGenerating && capabilities.videoGenerationReady,
  };
}

export function buildTemplateGenerateRequest({
  avatarTemplateId,
  scriptText,
  language,
  voice,
  speedRatio,
}: TemplateGenerateRequestInput) {
  return {
    avatar_template_id: avatarTemplateId,
    script_text: scriptText.trim(),
    language,
    voice,
    speed_ratio: speedRatio,
  };
}

export function getAvatarGenerationButtonLabelKey({
  action,
  isGenerating,
  healthChecking,
  healthUnavailable,
}: {
  action: AvatarGenerationAction;
  isGenerating: boolean;
  healthChecking: boolean;
  healthUnavailable: boolean;
}): AvatarGenerationButtonLabelKey {
  if (isGenerating) {
    return action.mode === "preview_tts" ? "generating_preview_tts" : "generating_video";
  }
  if (healthChecking) return "health_checking";
  if (healthUnavailable) {
    return action.mode === "preview_tts" ? "preview_tts_unavailable" : "video_unavailable";
  }
  return action.mode === "preview_tts" ? "generate_preview_tts" : "generate_video";
}

export function parsePreviewTtsReadyResponse(payload: unknown): PreviewTtsReadyResult | null {
  if (!payload || typeof payload !== "object") return null;
  const candidate = payload as Record<string, unknown>;
  if (
    candidate.preview_safe_mode !== true ||
    candidate.status !== "tts_ready" ||
    typeof candidate.audio_url !== "string" ||
    !candidate.audio_url.trim() ||
    candidate.task_id != null
  ) {
    return null;
  }
  return {
    audioUrl: candidate.audio_url,
    voice: typeof candidate.voice === "string" ? candidate.voice : undefined,
  };
}
