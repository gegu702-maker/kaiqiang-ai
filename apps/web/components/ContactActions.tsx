"use client";

import { Check, Copy, Mail, Phone } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { useLanguage } from "@/components/LanguageProvider";

const phone = "+86 17798561222";
const email = "17798561222@163.com";

type Tone = "light" | "dark";

const copy = {
  zh: {
    phone: "电话",
    email: "邮箱",
    copyPhone: "复制电话",
    copyEmail: "复制邮箱",
  },
  en: {
    phone: "Phone",
    email: "Email",
    copyPhone: "Copy Phone",
    copyEmail: "Copy Email",
  },
};

export function ContactActions({ tone = "light", compact = false, embedded = false }: { tone?: Tone; compact?: boolean; embedded?: boolean }) {
  const { locale } = useLanguage();
  const current = copy[locale === "zh" ? "zh" : "en"];
  const [copied, setCopied] = useState<"phone" | "email" | null>(null);
  const isDark = tone === "dark";

  async function copyValue(type: "phone" | "email", value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(type);
    window.setTimeout(() => setCopied(null), 1400);
  }

  const cardClass = isDark
    ? "border-white/10 bg-white/[0.04] text-slate-300"
    : "border-slate-200 bg-white/80 text-slate-600 shadow-[0_12px_34px_rgba(15,23,42,0.045)]";
  const labelClass = isDark ? "text-slate-400" : "text-slate-500";
  const valueClass = isDark ? "text-white" : "text-slate-950";
  const buttonClass = isDark
    ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]"
    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50";

  const wrapperClass = embedded
    ? `grid divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 ${isDark ? "divide-white/10" : "divide-slate-200"}`
    : compact
      ? "grid gap-3 sm:grid-cols-2"
      : "grid gap-4 sm:grid-cols-2";

  return (
    <div className={wrapperClass}>
      <ContactItem
        icon={<Phone size={17} />}
        label={current.phone}
        value={phone}
        href={`tel:${phone.replace(/\s/g, "")}`}
        copied={copied === "phone"}
        onCopy={() => copyValue("phone", phone)}
        cardClass={cardClass}
        labelClass={labelClass}
        valueClass={valueClass}
        buttonClass={buttonClass}
        compact={compact}
        embedded={embedded}
        copyLabel={current.copyPhone}
      />
      <ContactItem
        icon={<Mail size={17} />}
        label={current.email}
        value={email}
        href={`mailto:${email}`}
        copied={copied === "email"}
        onCopy={() => copyValue("email", email)}
        cardClass={cardClass}
        labelClass={labelClass}
        valueClass={valueClass}
        buttonClass={buttonClass}
        compact={compact}
        embedded={embedded}
        copyLabel={current.copyEmail}
      />
    </div>
  );
}

function ContactItem({
  icon,
  label,
  value,
  href,
  copied,
  onCopy,
  cardClass,
  labelClass,
  valueClass,
  buttonClass,
  compact,
  embedded,
  copyLabel,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  href: string;
  copied: boolean;
  onCopy: () => void;
  cardClass: string;
  labelClass: string;
  valueClass: string;
  buttonClass: string;
  compact: boolean;
  embedded: boolean;
  copyLabel: string;
}) {
  return (
    <div className={embedded ? `${compact ? "py-3 sm:px-4 sm:first:pl-0 sm:last:pr-0" : "py-4 sm:px-5 sm:first:pl-0 sm:last:pr-0"}` : `rounded-lg border ${cardClass} ${compact ? "p-4" : "p-5"} backdrop-blur-xl`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className={`flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] ${labelClass}`}>
            {icon}
            {label}
          </p>
          <a className={`mt-2 block break-words text-base font-semibold ${valueClass}`} href={href}>
            {value}
          </a>
        </div>
        <button
          type="button"
          onClick={onCopy}
          className={`inline-flex size-10 shrink-0 items-center justify-center rounded-full border transition ${buttonClass}`}
          aria-label={copyLabel}
          title={copyLabel}
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
      </div>
    </div>
  );
}

export const contactInfo = {
  phone,
  email,
};
