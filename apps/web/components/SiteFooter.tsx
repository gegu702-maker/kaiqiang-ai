"use client";

import Link from "next/link";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";
import { commonCopy } from "@/lib/i18n/common";

export function SiteFooter() {
  const { selectedLocale } = useLanguage();
  const current = commonCopy[selectedLocale].footer;

  return (
    <footer id="contact" className="border-t border-white/10 bg-ink px-4 py-10 text-slate-300 sm:px-6">
      <div className="mx-auto grid max-w-[1280px] gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <Link href="/" className="text-sm font-semibold tracking-[0.22em] text-white">
            KAIQIANG.AI
          </Link>
          <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
            {current.description}
          </p>
          <div className="mt-5 flex flex-wrap gap-4 text-sm text-slate-400">
            <Link className="hover:text-white" href="/pricing">
              {current.pricing}
            </Link>
            <Link className="hover:text-white" href="/studio/templates">
              {current.templates}
            </Link>
            <Link className="hover:text-white" href="/studio/avatar">
              {current.avatarStudio}
            </Link>
            <Link className="hover:text-white" href="/#contact">
              {current.contact}
            </Link>
          </div>
        </div>
        <div>
          <h2 className="text-sm font-semibold text-white">{current.contactTitle}</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">{current.contactBody}</p>
          <div className="mt-4">
            <ContactActions tone="dark" compact />
          </div>
        </div>
      </div>
    </footer>
  );
}
