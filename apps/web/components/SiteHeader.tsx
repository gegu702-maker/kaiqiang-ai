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
    <header className={isLanding ? "border-b border-slate-200 bg-[#f8f9ff]/90 text-slate-950 backdrop-blur" : "border-b border-white/10 bg-ink/80 text-slate-300 backdrop-blur"}>
      <nav className={isLanding ? "mx-auto grid max-w-[1440px] grid-cols-[1fr_auto] items-center gap-3 px-5 py-5 sm:px-8 lg:grid-cols-[1fr_auto_1fr] lg:px-14" : "mx-auto flex max-w-[1440px] items-center justify-between px-6 py-5 sm:px-10 lg:px-14"}>
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className={isLanding ? "relative size-11 overflow-hidden rounded-full border border-slate-200 bg-white" : "relative size-10 overflow-hidden rounded-full border border-white/15 bg-white"}>
            <Image src="/logo.png" alt="KAIQIANG.AI logo" fill sizes="40px" className="object-cover" priority />
          </span>
          <span className={isLanding ? "hidden text-base font-bold tracking-[0.28em] text-slate-950 min-[420px]:inline sm:text-xl" : "text-sm font-semibold tracking-[0.22em] text-white sm:text-base"}>KAIQIANG.AI</span>
        </Link>

        <div className={isLanding ? "hidden items-center justify-center gap-8 text-base font-semibold text-slate-950 lg:flex" : "flex items-center gap-1 text-sm text-slate-300 sm:gap-2"}>
          <Link className={isLanding ? "hidden rounded-md px-2 py-2 hover:bg-slate-200/60 sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/">
            {copy.home}
          </Link>
          <Link className={isLanding ? "hidden rounded-md px-2 py-2 hover:bg-slate-200/60 sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/pricing">
            {copy.pricing}
          </Link>
          <Link className={isLanding ? "hidden rounded-md px-2 py-2 hover:bg-slate-200/60 md:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 md:inline-flex"} href="/docs">
            {copy.docs}
          </Link>
        </div>

        <div className={isLanding ? "flex min-w-0 items-center justify-end gap-2 text-sm font-semibold text-slate-950 sm:gap-3" : "flex items-center gap-1 text-sm text-slate-300 sm:gap-2"}>
          <div className={isLanding ? "flex rounded-2xl border border-slate-200 bg-white p-1 text-base shadow-sm" : "flex rounded-md border border-white/10 bg-white/[0.03] p-1 text-xs"}>
            <button
              type="button"
              onClick={() => setLocale("zh")}
              className={locale === "zh" ? "rounded-xl bg-slate-950 px-3 py-2 text-white" : isLanding ? "px-3 py-2 text-slate-500 hover:text-slate-950" : "px-2 py-1 text-slate-400 hover:text-white"}
            >
              中文
            </button>
            <button
              type="button"
              onClick={() => setLocale("en")}
              className={locale === "en" ? "rounded-xl bg-slate-950 px-3 py-2 text-white" : isLanding ? "px-3 py-2 text-slate-500 hover:text-slate-950" : "px-2 py-1 text-slate-400 hover:text-white"}
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
