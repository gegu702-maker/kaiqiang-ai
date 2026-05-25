"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  const pathname = usePathname();
  const copy = navCopy[locale];
  const isLanding = pathname === "/";

  return (
    <header className={isLanding ? "sticky top-0 z-50 bg-transparent px-4 py-3 text-slate-950 sm:px-6" : "border-b border-white/10 bg-ink/80 text-slate-300 backdrop-blur"}>
      <nav className={isLanding ? "mx-auto grid h-16 max-w-[1360px] grid-cols-[1fr_auto] items-center gap-3 rounded-full border border-slate-200/75 bg-white/76 px-4 shadow-[0_12px_38px_rgba(15,23,42,0.055)] backdrop-blur-2xl sm:px-5 lg:grid-cols-[1fr_auto_1fr]" : "mx-auto flex max-w-[1440px] items-center justify-between px-6 py-5 sm:px-10 lg:px-14"}>
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className={isLanding ? "relative size-9 overflow-hidden rounded-full border border-slate-200/80 bg-white" : "relative size-10 overflow-hidden rounded-full border border-white/15 bg-white"}>
            <Image src="/logo.png" alt="KAIQIANG.AI logo" fill sizes="40px" className="object-cover" priority />
          </span>
          <span className={isLanding ? "hidden text-sm font-semibold tracking-[0.3em] text-slate-950 min-[420px]:inline" : "text-sm font-semibold tracking-[0.22em] text-white sm:text-base"}>KAIQIANG.AI</span>
        </Link>

        <div className={isLanding ? "hidden items-center justify-center gap-2 rounded-full bg-slate-100/55 p-1 text-sm font-medium text-slate-700 lg:flex" : "flex items-center gap-1 text-sm text-slate-300 sm:gap-2"}>
          <Link className={isLanding ? "hidden rounded-full px-4 py-2 transition hover:bg-white hover:text-slate-950 hover:shadow-sm sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/">
            {copy.home}
          </Link>
          <Link className={isLanding ? "hidden rounded-full px-4 py-2 transition hover:bg-white hover:text-slate-950 hover:shadow-sm sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/pricing">
            {copy.pricing}
          </Link>
          <Link className={isLanding ? "hidden rounded-full px-4 py-2 transition hover:bg-white hover:text-slate-950 hover:shadow-sm md:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 md:inline-flex"} href="/docs">
            {copy.docs}
          </Link>
        </div>

        <div className={isLanding ? "flex min-w-0 items-center justify-end gap-2 text-sm font-medium text-slate-700 sm:gap-3 [&_a]:rounded-full [&_a]:px-3 [&_a]:py-2 [&_a]:text-slate-700 [&_a]:transition [&_a:hover]:bg-slate-100 [&_a:hover]:text-slate-950 [&_button]:rounded-full [&_button]:px-3 [&_button]:py-2 [&_button]:text-slate-700 [&_button]:transition [&_button:hover]:bg-slate-100 [&_button:hover]:text-slate-950" : "flex items-center gap-1 text-sm text-slate-300 sm:gap-2"}>
          <div className={isLanding ? "flex rounded-full border border-slate-200/70 bg-white/70 p-0.5 text-xs" : "flex rounded-md border border-white/10 bg-white/[0.03] p-1 text-xs"}>
            <button
              type="button"
              onClick={() => setLocale("zh")}
              className={locale === "zh" ? "rounded-full bg-slate-900 px-3 py-1.5 text-white shadow-sm" : isLanding ? "px-3 py-1.5 text-slate-500 hover:text-slate-950" : "px-2 py-1 text-slate-400 hover:text-white"}
            >
              中文
            </button>
            <button
              type="button"
              onClick={() => setLocale("en")}
              className={locale === "en" ? "rounded-full bg-slate-900 px-3 py-1.5 text-white shadow-sm" : isLanding ? "px-3 py-1.5 text-slate-500 hover:text-slate-950" : "px-2 py-1 text-slate-400 hover:text-white"}
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
