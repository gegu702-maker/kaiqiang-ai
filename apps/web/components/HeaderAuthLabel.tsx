"use client";

import { useLanguage } from "@/components/LanguageProvider";

export function HeaderAuthLabel() {
  const { locale } = useLanguage();
  return <>{locale === "zh" ? "登录" : "Login"}</>;
}
