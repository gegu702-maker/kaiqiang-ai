"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Locale = "zh" | "en";

export const DEFAULT_LOCALE: Locale = "zh";
const STORAGE_KEY = "kaiqiang.locale";

export const SUPPORTED_LOCALES: Array<{ code: Locale; label: string; nativeName: string }> = [
  { code: "zh", label: "中文", nativeName: "中文" },
  { code: "en", label: "EN", nativeName: "English" },
];

export const SUPPORTED_LOCALE_CODES = SUPPORTED_LOCALES.map((locale) => locale.code);
type ContentLocale = "zh" | "en";

export function isSupportedLocale(value: unknown): value is Locale {
  return typeof value === "string" && SUPPORTED_LOCALE_CODES.includes(value as Locale);
}

export function normalizeLocale(value: unknown): Locale {
  if (typeof value !== "string") return DEFAULT_LOCALE;
  const normalized = value.trim().toLowerCase();
  if (normalized === "zh" || normalized === "zh-cn" || normalized === "zh_cn" || normalized === "中文") return "zh";
  if (normalized === "en" || normalized === "en-us" || normalized === "en_us" || normalized === "english") return "en";
  return DEFAULT_LOCALE;
}

function toStoredLocale(locale: Locale): "zh-CN" | "en-US" {
  return locale === "en" ? "en-US" : "zh-CN";
}

type LanguageContextValue = {
  locale: ContentLocale;
  selectedLocale: Locale;
  setLocale: (locale: Locale) => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [selectedLocale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);
  const locale = toContentLocale(selectedLocale);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const safeLocale = normalizeLocale(saved);
    setLocaleState(safeLocale);
    if (saved !== toStoredLocale(safeLocale)) {
      window.localStorage.setItem(STORAGE_KEY, toStoredLocale(safeLocale));
    }
  }, []);

  const value = useMemo(
    () => ({
      locale,
      selectedLocale,
      setLocale: (nextLocale: Locale) => {
        const safeLocale = normalizeLocale(nextLocale);
        setLocaleState(safeLocale);
        window.localStorage.setItem(STORAGE_KEY, toStoredLocale(safeLocale));
      },
    }),
    [locale, selectedLocale],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

function toContentLocale(locale: Locale): ContentLocale {
  return locale === "zh" ? "zh" : "en";
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }
  return context;
}
