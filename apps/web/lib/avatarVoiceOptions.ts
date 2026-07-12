export const DEFAULT_AVATAR_VOICE_KEY = "zh_female_default";

export const avatarVoiceOptions = [
  {
    key: DEFAULT_AVATAR_VOICE_KEY,
    name: { zh: "通用音色", en: "General voice" },
    description: { zh: "自然清晰，适合大多数短视频口播", en: "Clear and natural for most talking videos" },
    recommended: true,
    recommendedSpeed: 1,
  },
] as const;

export type AvatarVoiceKey = (typeof avatarVoiceOptions)[number]["key"];
