"use client";

import Link from "next/link";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    description: "Kaiqiang AI 专注于数字人视频、AI 口播生成和创作者内容工具。",
    pricing: "定价",
    templates: "模板",
    avatarStudio: "数字人工作台",
    contact: "联系",
    contactTitle: "联系我们",
    contactBody: "需要商务咨询、定制模板或生成支持，可以直接联系。",
  },
  en: {
    description: "AI Avatar Generator for digital human videos, talking avatar workflows, and creator-ready AI video generation.",
    pricing: "Pricing",
    templates: "Templates",
    avatarStudio: "Avatar Studio",
    contact: "Contact",
    contactTitle: "Contact",
    contactBody: "Need business consultation, custom templates, or generation support? Feel free to contact us.",
  },
};

export function SiteFooter() {
  const { locale } = useLanguage();
  const current = copy[locale];

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
