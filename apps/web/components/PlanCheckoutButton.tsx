"use client";

import { useActionState } from "react";
import { CreditCard } from "lucide-react";

import { createPlaceholderOrderAction } from "@/app/actions/billing";

const initialState = { ok: false, message: "" };

export function PlanCheckoutButton({ plan }: { plan: "plus" | "pro" | "business" }) {
  const [state, action] = useActionState(createPlaceholderOrderAction, initialState);

  return (
    <form action={action} className="mt-6 space-y-3">
      <input type="hidden" name="plan" value={plan} />
      <div className="grid gap-2 sm:grid-cols-3">
        <select name="billing_cycle" defaultValue="monthly" className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-xs text-slate-200">
          <option value="monthly">月付</option>
          <option value="yearly">年付 省约 17%</option>
        </select>
        <select name="currency" defaultValue="CNY" className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-xs text-slate-200">
          <option value="CNY">人民币</option>
          <option value="USD">USD</option>
        </select>
        <select name="provider" defaultValue="stripe" className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-xs text-slate-200">
          <option value="stripe">Stripe</option>
          <option value="lemon_squeezy">Lemon Squeezy</option>
          <option value="creem">Creem</option>
          <option value="pingpp">Ping++</option>
          <option value="manual">人工开通</option>
        </select>
      </div>
      <button className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90">
        <CreditCard size={16} />
        {plan === "plus" ? "升级 Plus" : plan === "pro" ? "升级 Pro" : "创建 Business 咨询订单"}
      </button>
      {state.message ? <p className={state.ok ? "text-xs text-lime" : "text-xs text-rose-200"}>{state.message}</p> : null}
    </form>
  );
}
