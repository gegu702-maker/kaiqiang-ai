export const DEFAULT_AVATAR_VOICE_KEY = "zh_female_default";

export type AvatarVoiceLanguage = "zh-CN" | "en-US" | "ja-JP";
export type AvatarVoiceGroup = "zh" | "en" | "ja";

export const avatarVoiceGroups = [
  { key: "zh", name: { zh: "中文 / 方言", en: "Chinese / Dialects" } },
  { key: "en", name: { zh: "英语", en: "English" } },
  { key: "ja", name: { zh: "日语", en: "Japanese" } },
] as const;

export const avatarVoiceOptions = [
  {
    key: DEFAULT_AVATAR_VOICE_KEY,
    language: "zh-CN",
    group: "zh",
    name: { zh: "中文女声", en: "Chinese Female" },
    description: { zh: "自然清晰，适合大多数短视频口播", en: "Clear and natural for most talking videos" },
    recommended: true,
    recommendedSpeed: 1,
  },
  { key: "zh_male_default", language: "zh-CN", group: "zh", name: { zh: "中文男声", en: "Chinese Male" }, description: { zh: "自然沉稳，适合中文口播", en: "Natural and steady Mandarin" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_dongbei_laotie", language: "zh-CN", group: "zh", name: { zh: "东北老铁", en: "Northeastern Chinese Male" }, description: { zh: "东北话，亲切豪爽", en: "Friendly Northeastern Chinese dialect" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_gentle_young_man", language: "zh-CN", group: "zh", name: { zh: "温柔小哥", en: "Gentle Young Man" }, description: { zh: "温柔自然的中文男声", en: "Gentle natural Mandarin male" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_refined_youth", language: "zh-CN", group: "zh", name: { zh: "儒雅青年", en: "Refined Young Man" }, description: { zh: "儒雅沉稳的中文男声", en: "Refined steady Mandarin male" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_sunny_male", language: "zh-CN", group: "zh", name: { zh: "阳光男声", en: "Sunny Male" }, description: { zh: "明朗有活力的中文男声", en: "Bright energetic Mandarin male" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_intellectual_female_bilingual", language: "zh-CN", group: "zh", name: { zh: "知性姐姐-双语", en: "Intellectual Female - Bilingual" }, description: { zh: "控制台语种为中文", en: "Bilingual voice configured as Chinese" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_friendly_female", language: "zh-CN", group: "zh", name: { zh: "亲切女声", en: "Friendly Female" }, description: { zh: "亲切自然的中文女声", en: "Friendly natural Mandarin female" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_guangxi_cousin", language: "zh-CN", group: "zh", name: { zh: "广西表哥", en: "Guangxi Male" }, description: { zh: "广西普通话，轻松亲切", en: "Relaxed Guangxi-accented Mandarin" }, recommended: false, recommendedSpeed: 1 },
  { key: "zh_lively_female", language: "zh-CN", group: "zh", name: { zh: "活泼女声", en: "Lively Female" }, description: { zh: "活泼明快的中文女声", en: "Lively bright Mandarin female" }, recommended: false, recommendedSpeed: 1 },
  { key: "en_energetic_male_jackson", language: "en-US", group: "en", name: { zh: "活力男声-Jackson（英语）", en: "Energetic Male - Jackson" }, description: { zh: "英语男声", en: "Energetic English male" }, recommended: false, recommendedSpeed: 1 },
  { key: "en_energetic_female_ariana", language: "en-US", group: "en", name: { zh: "活力女声-Ariana（英语）", en: "Energetic Female - Ariana" }, description: { zh: "英语女声", en: "Energetic English female" }, recommended: false, recommendedSpeed: 1 },
  { key: "ja_male", language: "ja-JP", group: "ja", name: { zh: "日语男声（日语）", en: "Japanese Male" }, description: { zh: "日语男声", en: "Japanese male" }, recommended: false, recommendedSpeed: 1 },
  { key: "ja_elegant_female", language: "ja-JP", group: "ja", name: { zh: "气质女生（日语）", en: "Elegant Female (Japanese)" }, description: { zh: "日语女声，请输入日语文案", en: "Japanese female; use a Japanese script" }, recommended: false, recommendedSpeed: 1 },
] as const;

export type AvatarVoiceKey = (typeof avatarVoiceOptions)[number]["key"];

export function getAvatarVoiceLanguage(voiceKey: AvatarVoiceKey): AvatarVoiceLanguage {
  return avatarVoiceOptions.find((option) => option.key === voiceKey)?.language ?? "zh-CN";
}

export function getAvatarVoicePreviewAudioPath(voiceKey: AvatarVoiceKey): string {
  return `/audio/voice-previews/${voiceKey}.mp3`;
}
