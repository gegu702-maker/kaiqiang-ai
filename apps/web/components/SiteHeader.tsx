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
    <header className={isLanding ? "border-b border-neutral-200 bg-[#f7f7f4]/90 text-neutral-900 backdrop-blur" : "border-b border-white/10 bg-ink/80 text-slate-300 backdrop-blur"}>
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className={isLanding ? "relative size-10 overflow-hidden rounded-full border border-neutral-200 bg-white" : "relative size-10 overflow-hidden rounded-full border border-white/15 bg-white"}>
            <Image src="/logo.png" alt="KAIQIANG.AI logo" fill sizes="40px" className="object-cover" priority />
          </span>
          <span className={isLanding ? "text-sm font-semibold tracking-[0.22em] text-neutral-950 sm:text-base" : "text-sm font-semibold tracking-[0.22em] text-white sm:text-base"}>KAIQIANG.AI</span>
        </Link>

        <div className={isLanding ? "flex items-center gap-1 text-sm text-neutral-700 sm:gap-2" : "flex items-center gap-1 text-sm text-slate-300 sm:gap-2"}>
          <Link className={isLanding ? "hidden rounded-md px-3 py-2 hover:bg-neutral-200/70 sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/">
            {copy.home}
          </Link>
          <Link className={isLanding ? "hidden rounded-md px-3 py-2 hover:bg-neutral-200/70 sm:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex"} href="/pricing">
            {copy.pricing}
          </Link>
          <Link className={isLanding ? "hidden rounded-md px-3 py-2 hover:bg-neutral-200/70 md:inline-flex" : "hidden rounded-md px-3 py-2 hover:bg-white/10 md:inline-flex"} href="/docs">
            {copy.docs}
          </Link>
          <div className={isLanding ? "mx-1 hidden h-5 w-px bg-neutral-200 sm:block" : "mx-1 hidden h-5 w-px bg-white/10 sm:block"} />
          <div className={isLanding ? "flex rounded-md border border-neutral-200 bg-white p-1 text-xs" : "flex rounded-md border border-white/10 bg-white/[0.03] p-1 text-xs"}>
            <button
              type="button"
              onClick={() => setLocale("zh")}
              className={locale === "zh" ? "rounded bg-neutral-950 px-2 py-1 text-white" : isLanding ? "px-2 py-1 text-neutral-500 hover:text-neutral-950" : "px-2 py-1 text-slate-400 hover:text-white"}
            >
              中文
            </button>
            <button
              type="button"
              onClick={() => setLocale("en")}
              className={locale === "en" ? "rounded bg-neutral-950 px-2 py-1 text-white" : isLanding ? "px-2 py-1 text-neutral-500 hover:text-neutral-950" : "px-2 py-1 text-slate-400 hover:text-white"}
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
