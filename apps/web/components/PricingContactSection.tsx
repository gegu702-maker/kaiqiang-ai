"use client";

import { ContactActions } from "@/components/ContactActions";
import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    label: "联系我们",
    title: "需要定制套餐或商务支持？",
    body: "如需团队额度、定制模板或上线前咨询，可以直接联系。",
  },
  en: {
    label: "Contact",
    title: "Need a custom plan or business support?",
    body: "Reach out for team credits, custom templates, or pre-launch questions.",
  },
};

export function PricingContactSection() {
  const { locale } = useLanguage();
  const current = copy[locale];

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
