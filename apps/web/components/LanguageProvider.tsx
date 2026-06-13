"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Locale = "zh" | "en" | "ja" | "ko" | "es" | "fr" | "ru";

export const DEFAULT_LOCALE: Locale = "zh";

export const SUPPORTED_LOCALES: Array<{ code: Locale; label: string; nativeName: string }> = [
  { code: "zh", label: "中文", nativeName: "中文" },
  { code: "en", label: "EN", nativeName: "English" },
  { code: "ja", label: "日本語", nativeName: "日本語" },
  { code: "ko", label: "한국어", nativeName: "한국어" },
  { code: "es", label: "ES", nativeName: "Español" },
  { code: "fr", label: "FR", nativeName: "Français" },
  { code: "ru", label: "RU", nativeName: "Русский" },
];

export const SUPPORTED_LOCALE_CODES = SUPPORTED_LOCALES.map((locale) => locale.code);

export function isSupportedLocale(value: unknown): value is Locale {
  return typeof value === "string" && SUPPORTED_LOCALE_CODES.includes(value as Locale);
}

type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const saved = window.localStorage.getItem("kaiqiang.locale");
    if (isSupportedLocale(saved)) {
      setLocaleState(saved);
    }
  }, []);

  const value = useMemo(
    () => ({
      locale,
      setLocale: (nextLocale: Locale) => {
        const safeLocale = isSupportedLocale(nextLocale) ? nextLocale : DEFAULT_LOCALE;
        setLocaleState(safeLocale);
        window.localStorage.setItem("kaiqiang.locale", safeLocale);
      },
    }),
    [locale],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }
  return context;
}
