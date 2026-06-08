"use client";

import Link from "next/link";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";
import { navigationCopy } from "@/lib/i18n/navigation";

const copy = {
  zh: {
    description: "Kaiqiang.ai 帮助创作者从爆款链接拆解、AI 仿写到数字人口播视频导出，一套流程完成内容生产。",
    contact: "联系",
    contactTitle: "联系我们",
    contactBody: "需要商务咨询、定制模板或生成支持，可以直接联系。",
  },
  en: {
    description: "Kaiqiang.ai helps creators turn viral links into original scripts and talking-avatar videos in one workflow.",
    contact: "Contact",
    contactTitle: "Contact",
    contactBody: "Need business consultation, custom templates, or generation support? Feel free to contact us.",
  },
};

export function SiteFooter() {
  const { locale } = useLanguage();
  const current = copy[locale];
  const nav = navigationCopy[locale];

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
              {nav.pricing}
            </Link>
            <Link className="hover:text-white" href="/studio/templates">
              {nav.templates}
            </Link>
            <Link className="hover:text-white" href="/studio">
              {nav.studio}
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
