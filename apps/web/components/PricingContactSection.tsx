"use client";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";
import { commonCopy } from "@/lib/i18n/common";

export function PricingContactSection() {
  const { selectedLocale } = useLanguage();
  const current = commonCopy[selectedLocale].pricingContact;

  return (
    <section className="mt-6 rounded-lg border border-white/10 bg-panel/70 p-5 shadow-glow">
      <div className="grid gap-5 lg:grid-cols-[0.78fr_1.22fr] lg:items-center">
        <div>
          <p className="text-sm font-medium text-cyan">{current.label}</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">{current.title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{current.body}</p>
        </div>
        <ContactActions tone="dark" compact embedded />
      </div>
    </section>
  );
}
