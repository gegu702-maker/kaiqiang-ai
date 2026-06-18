"use client";

import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { useLanguage } from "@/components/LanguageProvider";
import { PlanCheckoutButton } from "@/components/PlanCheckoutButton";
import { PricingContactSection } from "@/components/PricingContactSection";
import { pricingCopy } from "@/lib/i18n/pricing";

export default function PricingPage() {
  const { selectedLocale } = useLanguage();
  const current = pricingCopy[selectedLocale];

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm font-medium text-cyan">{current.eyebrow}</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">{current.title}</h1>
        <p className="mt-3 text-slate-400">
          {current.subtitle}
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-4">
        {current.plans.map((plan) => (
          <section key={plan.name} className={plan.code === "plus" ? "relative rounded-lg border border-cyan/45 bg-panel/90 p-5 shadow-glow" : plan.code === "pro" ? "relative rounded-lg border border-lime/35 bg-panel/85 p-5 shadow-glow" : "relative rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow"}>
            {"badge" in plan ? <span className="absolute right-4 top-4 rounded-full bg-cyan px-3 py-1 text-xs font-semibold text-ink">{plan.badge}</span> : null}
            <h2 className="text-2xl font-semibold text-white">{plan.name}</h2>
            <div className="mt-4">
              <span className="text-4xl font-semibold text-cyan">{plan.price}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">{plan.desc}</p>
            <ul className="mt-5 space-y-3 text-sm text-slate-300">
              {plan.features.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-lime" />
                  {item}
                </li>
              ))}
            </ul>
            {plan.code === "free" ? (
              <Link
                href="/login?next=/studio"
                className="mt-6 flex h-11 items-center justify-center rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90"
              >
                {plan.buttonLabel}
              </Link>
            ) : (
              <PlanCheckoutButton plan={plan.code} />
            )}
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.04] p-5 text-sm leading-6 text-slate-400">
        {current.note}
      </div>

      <div id="pricing-contact">
        <PricingContactSection />
      </div>
    </main>
  );
}
