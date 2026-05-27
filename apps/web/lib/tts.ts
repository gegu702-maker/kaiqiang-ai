export const ttsVoiceLabels: Record<string, string> = {
  minimax_zh_female: "MiniMax 中文女声",
  minimax_en_female: "MiniMax English Female",
  BV001_streaming: "火山引擎 BV001 女声",
  BV002_streaming: "火山引擎 BV002 男声",
};

export function getTTSVoiceLabel(voiceName: string) {
  return ttsVoiceLabels[voiceName] ?? voiceName;
}

export function getLanguageLabel(language: string) {
  if (language === "zh") return "中文";
  if (language === "en") return "English";
  return language;
}
