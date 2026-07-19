export const DEFAULT_AVATAR_VOICE_KEY = "zh_female_default";

export const avatarVoiceOptions = [
  {
    key: DEFAULT_AVATAR_VOICE_KEY,
    name: { zh: "中文女声", en: "Chinese Female" },
    description: { zh: "自然清晰，适合大多数短视频口播", en: "Clear and natural for most talking videos" },
    recommended: true,
    recommendedSpeed: 1,
  },
  {
    key: "zh_male_default",
    name: { zh: "中文男声", en: "Chinese Male" },
    description: { zh: "自然沉稳，适合中文口播", en: "Natural and steady for Chinese talking videos" },
    recommended: false,
    recommendedSpeed: 1,
  },
] as const;

export type AvatarVoiceKey = (typeof avatarVoiceOptions)[number]["key"];
