"use client";

import { Check, ChevronDown, Languages, Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { SUPPORTED_LOCALES, useLanguage, type Locale } from "@/components/LanguageProvider";
import { mainNavigationItems, navigationCopy } from "@/lib/i18n/navigation";

export function SiteHeader({ authSlot }: { authSlot: ReactNode }) {
  const { locale, setLocale } = useLanguage();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const copy = navigationCopy[locale];
  const isLanding = pathname === "/";
  const navItems = mainNavigationItems.map((item) => ({ href: item.href, label: copy[item.key] }));
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
          <LanguageDropdown
            ariaLabel={copy.language}
            locale={locale}
            onLocaleChange={setLocale}
          />
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

function LanguageDropdown({
  ariaLabel,
  locale,
  onLocaleChange,
}: {
  ariaLabel: string;
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
}) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const activeLocale = SUPPORTED_LOCALES.find((item) => item.code === locale) ?? SUPPORTED_LOCALES[0];

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  return (
    <div ref={dropdownRef} className="relative shrink-0">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((value) => !value)}
        className="!inline-flex h-10 min-w-[118px] !items-center !justify-between gap-2 !rounded-full border border-cyan/35 bg-ink/92 px-3 !py-0 text-xs font-semibold !text-white shadow-[0_0_24px_rgba(49,215,255,0.16)] outline-none transition hover:border-cyan/70 hover:bg-slate-950 focus-visible:ring-2 focus-visible:ring-cyan/60 sm:min-w-[132px]"
      >
        <span className="inline-flex min-w-0 items-center gap-2">
          <Languages size={15} className="shrink-0 text-cyan" />
          <span className="truncate">{activeLocale.nativeName}</span>
        </span>
        <ChevronDown size={15} className={open ? "shrink-0 text-cyan transition rotate-180" : "shrink-0 text-cyan transition"} />
      </button>

      {open ? (
        <div
          className="absolute right-0 top-[calc(100%+10px)] z-50 w-44 overflow-hidden rounded-lg border border-[rgba(0,212,255,.35)] bg-[#07111d] p-1.5 text-sm !text-white shadow-[0_18px_50px_rgba(0,0,0,0.45),0_0_32px_rgba(49,215,255,0.15)] backdrop-blur-xl"
          role="listbox"
          aria-label={ariaLabel}
        >
          {SUPPORTED_LOCALES.map((item) => {
            const selected = item.code === locale;
            return (
              <button
                key={item.code}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => {
                  onLocaleChange(item.code);
                  setOpen(false);
                }}
                className={[
                  "!flex h-10 w-full !items-center !justify-between rounded-md px-3 !py-0 text-left text-sm font-semibold outline-none transition",
                  selected
                    ? "bg-white/[0.08] !text-[#00d4ff] shadow-[inset_0_0_0_1px_rgba(0,212,255,.35)]"
                    : "!text-white hover:bg-white/[0.08] hover:!text-white focus-visible:bg-white/[0.08] focus-visible:!text-white",
                ].join(" ")}
              >
                <span>{item.nativeName}</span>
                {selected ? <Check size={15} /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
