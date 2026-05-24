"use client";

import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { useLanguage } from "@/components/LanguageProvider";

const navCopy = {
  zh: {
    home: "首页",
    pricing: "定价",
    docs: "文档",
  },
  en: {
    home: "Home",
    pricing: "Pricing",
    docs: "Docs",
  },
};

export function SiteHeader({ authSlot }: { authSlot: ReactNode }) {
  const { locale, setLocale } = useLanguage();
  const copy = navCopy[locale];

  return (
    <header className="border-b border-white/10 bg-ink/80 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className="relative size-10 overflow-hidden rounded-full border border-white/15 bg-white">
            <Image src="/logo.png" alt="KAIQIANG.AI logo" fill sizes="40px" className="object-cover" priority />
          </span>
          <span className="text-sm font-semibold tracking-[0.22em] text-white sm:text-base">KAIQIANG.AI</span>
        </Link>

        <div className="flex items-center gap-1 text-sm text-slate-300 sm:gap-2">
          <Link className="hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex" href="/">
            {copy.home}
          </Link>
          <Link className="hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex" href="/pricing">
            {copy.pricing}
          </Link>
          <Link className="hidden rounded-md px-3 py-2 hover:bg-white/10 md:inline-flex" href="/docs">
            {copy.docs}
          </Link>
          <div className="mx-1 hidden h-5 w-px bg-white/10 sm:block" />
          <div className="flex rounded-md border border-white/10 bg-white/[0.03] p-1 text-xs">
            <button
              type="button"
              onClick={() => setLocale("zh")}
              className={locale === "zh" ? "rounded bg-white px-2 py-1 text-ink" : "px-2 py-1 text-slate-400 hover:text-white"}
            >
              中文
            </button>
            <button
              type="button"
              onClick={() => setLocale("en")}
              className={locale === "en" ? "rounded bg-white px-2 py-1 text-ink" : "px-2 py-1 text-slate-400 hover:text-white"}
            >
              EN
            </button>
          </div>
          {authSlot}
        </div>
      </nav>
    </header>
  );
}
