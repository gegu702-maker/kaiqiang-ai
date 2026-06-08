export const ttsVoiceLabels: Record<string, string> = {
  minimax_zh_female: "Kaiqiang 中文女声",
  minimax_en_female: "Kaiqiang English Female",
  BV001_streaming: "Kaiqiang 女声",
  BV002_streaming: "Kaiqiang 男声",
};

export function getTTSVoiceLabel(voiceName: string) {
  return ttsVoiceLabels[voiceName] ?? voiceName;
}

export function getLanguageLabel(language: string) {
  if (language === "zh") return "中文";
  if (language === "en") return "English";
  return language;
}
