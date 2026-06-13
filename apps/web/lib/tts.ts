import type { Locale } from "@/components/LanguageProvider";

export const ttsVoiceLabels: Record<string, string> = {
  minimax_zh_female: "Kaiqiang 中文女声",
  minimax_en_female: "Kaiqiang English Female",
  BV001_streaming: "Kaiqiang 女声",
  BV002_streaming: "Kaiqiang 男声",
};

// TODO: Replace fallback voice_type values with provider-confirmed multilingual voices.
export const defaultVoiceTypeByLocale: Record<Locale, string> = {
  zh: "BV001_streaming",
  en: "BV001_streaming",
  ja: "BV001_streaming",
  ko: "BV001_streaming",
  es: "BV001_streaming",
  fr: "BV001_streaming",
  ru: "BV001_streaming",
};

export function getDefaultVoiceTypeForLocale(locale: Locale) {
  return defaultVoiceTypeByLocale[locale] ?? defaultVoiceTypeByLocale.en;
}

export function getTTSVoiceLabel(voiceName: string) {
  return ttsVoiceLabels[voiceName] ?? voiceName;
}

export function getLanguageLabel(language: string) {
  if (language === "zh") return "中文";
  if (language === "en") return "English";
  if (language === "ja") return "日本語";
  if (language === "ko") return "한국어";
  if (language === "es") return "Español";
  if (language === "fr") return "Français";
  if (language === "ru") return "Русский";
  return language;
}
