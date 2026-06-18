"use client";

import { useActionState } from "react";
import { CreditCard } from "lucide-react";

import { createPlaceholderOrderAction } from "@/app/actions/billing";
import { useLanguage } from "@/components/LanguageProvider";
import { pricingCopy } from "@/lib/i18n/pricing";

const initialState = { ok: false, message: "" };

export function PlanCheckoutButton({ plan }: { plan: "plus" | "pro" | "business" }) {
  const { selectedLocale } = useLanguage();
  const current = pricingCopy[selectedLocale];
  const [state, action] = useActionState(createPlaceholderOrderAction, initialState);
  const isBusiness = plan === "business";
  const planCopy = current.plans.find((item) => item.code === plan);

  return (
    <form action={action} className="mt-6 space-y-3">
      <input type="hidden" name="plan" value={plan} />
      <input type="hidden" name="provider" value={isBusiness ? "manual" : "stripe"} />
      <div className="grid gap-2 sm:grid-cols-2">
        <select name="billing_cycle" defaultValue="monthly" className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-xs text-slate-200">
          <option value="monthly">{current.billingMonthly}</option>
          <option value="yearly">{current.billingYearly}</option>
        </select>
        <select name="currency" defaultValue="CNY" className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-xs text-slate-200">
          <option value="CNY">{current.currencyCny}</option>
          <option value="USD">{current.currencyUsd}</option>
        </select>
      </div>
      <button className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90">
        <CreditCard size={16} />
        {planCopy?.buttonLabel}
      </button>
      {state.message ? <p className={state.ok ? "text-xs text-lime" : "text-xs text-rose-200"}>{state.message}</p> : null}
    </form>
  );
}
