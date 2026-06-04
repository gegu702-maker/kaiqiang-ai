"use client";

import { Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";

const navCopy = {
  zh: {
    home: "首页",
    pricing: "定价",
    templates: "模板",
    avatarStudio: "数字人工作台",
    contact: "联系",
    menu: "菜单",
  },
  en: {
    home: "Home",
    pricing: "Pricing",
    templates: "Templates",
    avatarStudio: "Avatar Studio",
    contact: "Contact",
    menu: "Menu",
  },
};

export function SiteHeader({ authSlot }: { authSlot: ReactNode }) {
  const { locale, setLocale } = useLanguage();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const copy = navCopy[locale];
  const isLanding = pathname === "/";
  const navItems = [
    { href: "/", label: copy.home },
    { href: "/pricing", label: copy.pricing },
    { href: "/studio/templates", label: copy.templates },
    { href: "/studio/avatar", label: copy.avatarStudio },
    { href: "/#contact", label: copy.contact },
  ];
  const desktopLinkClass = isLanding
    ? "rounded-full px-4 py-2 transition hover:bg-white hover:text-slate-950 hover:shadow-sm"
    : "rounded-md px-3 py-2 hover:bg-white/10";

  return (
    <header className={isLanding ? "sticky top-0 z-50 bg-transparent px-4 py-3 text-slate-950 sm:px-6" : "sticky top-0 z-50 border-b border-white/10 bg-ink/90 text-slate-300 backdrop-blur"}>
      <nav className={isLanding ? "relative mx-auto grid min-h-16 max-w-[1360px] grid-cols-[1fr_auto] items-center gap-3 rounded-full border border-slate-200/75 bg-white/76 px-4 py-2 shadow-[0_12px_38px_rgba(15,23,42,0.055)] backdrop-blur-2xl sm:px-5 lg:grid-cols-[1fr_auto_1fr]" : "relative mx-auto flex max-w-[1440px] items-center justify-between px-4 py-4 sm:px-6 lg:px-14"}>
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className={isLanding ? "relative size-9 overflow-hidden rounded-full border border-slate-200/80 bg-white" : "relative size-10 overflow-hidden rounded-full border border-white/15 bg-white"}>
            <Image src="/logo.png" alt="KAIQIANG.AI logo" fill sizes="40px" className="object-cover" priority />
          </span>
          <span className={isLanding ? "hidden text-sm font-semibold tracking-[0.3em] text-slate-950 min-[420px]:inline" : "text-sm font-semibold tracking-[0.22em] text-white sm:text-base"}>KAIQIANG.AI</span>
        </Link>

        <div className={isLanding ? "hidden items-center justify-center gap-1 rounded-full bg-slate-100/55 p-1 text-sm font-medium text-slate-700 lg:flex" : "hidden items-center gap-1 text-sm text-slate-300 lg:flex"}>
          {navItems.map((item) => (
            <Link key={item.href} className={desktopLinkClass} href={item.href}>
              {item.label}
            </Link>
          ))}
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
          <div className="hidden sm:block">{authSlot}</div>
          <button
            type="button"
            onClick={() => setMobileOpen((value) => !value)}
            className={isLanding ? "inline-flex size-10 items-center justify-center rounded-full border border-slate-200/70 bg-white/70 text-slate-800 lg:hidden" : "inline-flex size-10 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-white lg:hidden"}
            aria-label={copy.menu}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
        {mobileOpen ? (
          <div className={isLanding ? "absolute left-0 right-0 top-[calc(100%+10px)] rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_18px_42px_rgba(15,23,42,0.12)] lg:hidden" : "absolute left-4 right-4 top-[calc(100%+8px)] rounded-lg border border-white/10 bg-ink p-3 shadow-glow lg:hidden"}>
            <div className="grid gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  className={isLanding ? "rounded-lg px-3 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-100" : "rounded-md px-3 py-3 text-sm font-semibold text-slate-200 hover:bg-white/10"}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                >
                  {item.label}
                </Link>
              ))}
            </div>
            <div className={isLanding ? "mt-2 border-t border-slate-200 pt-2 sm:hidden" : "mt-2 border-t border-white/10 pt-2 sm:hidden"}>{authSlot}</div>
          </div>
        ) : null}
      </nav>
    </header>
  );
}
