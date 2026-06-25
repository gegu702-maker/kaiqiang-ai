export type DubbingLanguageCode = "zh-CN" | "en-US" | "ja-JP" | "ko-KR";

export type DubbingVoice = {
  id: string;
  label: string;
  gender: "female" | "male" | "neutral";
  provider: "volcengine";
  language: DubbingLanguageCode;
  enabled: boolean;
};

export type DubbingLanguage = {
  code: DubbingLanguageCode;
  label: string;
  nativeLabel: string;
  enabled: boolean;
  comingSoon: boolean;
  voices: DubbingVoice[];
};

export const DEFAULT_DUBBING_LANGUAGE: DubbingLanguageCode = "zh-CN";
export const DEFAULT_DUBBING_VOICE = "BV001_streaming";

export const dubbingLanguages: DubbingLanguage[] = [
  {
    code: "zh-CN",
    label: "Chinese Mandarin",
    nativeLabel: "中文普通话",
    enabled: true,
    comingSoon: false,
    voices: [
      {
        id: "BV001_streaming",
        label: "Mandarin female",
        gender: "female",
        provider: "volcengine",
        language: "zh-CN",
        enabled: true,
      },
      {
        id: "BV002_streaming",
        label: "Mandarin male",
        gender: "male",
        provider: "volcengine",
        language: "zh-CN",
        enabled: true,
      },
    ],
  },
  {
    code: "en-US",
    label: "English",
    nativeLabel: "English",
    enabled: false,
    comingSoon: true,
    voices: [],
  },
  {
    code: "ja-JP",
    label: "Japanese",
    nativeLabel: "日本語",
    enabled: false,
    comingSoon: true,
    voices: [],
  },
  {
    code: "ko-KR",
    label: "Korean",
    nativeLabel: "한국어",
    enabled: false,
    comingSoon: true,
    voices: [],
  },
];

export function getEnabledDubbingVoices(registry: DubbingLanguage[], languageCode: string) {
  return registry.find((language) => language.code === languageCode)?.voices.filter((voice) => voice.enabled) ?? [];
}

export function getDefaultVoiceForLanguage(registry: DubbingLanguage[], languageCode: string) {
  return getEnabledDubbingVoices(registry, languageCode)[0]?.id ?? DEFAULT_DUBBING_VOICE;
}
