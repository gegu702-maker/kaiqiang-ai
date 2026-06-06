import Link from "next/link";
import { ArrowLeft, BadgeDollarSign, Gauge, UsersRound } from "lucide-react";

import { AdminPlanForm } from "@/components/AdminCommercialForms";
import { Button } from "@/components/ui/button";
import { getAdminPlans } from "@/lib/api";
import { requireAdmin } from "@/lib/adminAuth";
import type { Plan } from "@/lib/types";

function formatPrice(cents: number) {
  return `¥${(cents / 100).toFixed(2)}`;
}

export default async function AdminPlansPage() {
  await requireAdmin("/admin/plans");

  let plans: Plan[] = [];
  let error = "";

  try {
    plans = await getAdminPlans();
  } catch (err) {
    error = err instanceof Error ? err.message : "套餐数据加载失败";
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Button asChild variant="ghost" size="sm" className="-ml-3">
          <Link href="/admin">
            <ArrowLeft size={16} />
            返回
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/admin/users">
            <UsersRound size={16} />
            用户管理
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/admin/quotas">
            <Gauge size={16} />
            额度管理
          </Link>
        </Button>
      </div>

      <div className="mb-6">
        <p className="text-sm text-cyan">Plans</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">套餐管理</h1>
        <p className="mt-2 text-slate-400">维护套餐额度、价格、声音克隆权限和前台可用状态。</p>
      </div>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <section className="grid gap-4">
        {plans.map((plan) => (
          <article key={plan.code} className="rounded-lg border border-white/10 bg-panel/80 p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <BadgeDollarSign className="text-cyan" size={20} />
                  <h2 className="text-xl font-semibold text-white">{plan.code.toUpperCase()}</h2>
                  <span className={plan.is_active ? "rounded-full border border-lime/20 bg-lime/10 px-2 py-1 text-xs text-lime" : "rounded-full border border-white/10 px-2 py-1 text-xs text-slate-400"}>
                    {plan.is_active ? "active" : "hidden"}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  月额度 {plan.monthly_quota ?? "不限"} · 月付 {formatPrice(plan.monthly_price_cny)} · 年付 {formatPrice(plan.yearly_price_cny)}
                </p>
              </div>
              <span className="rounded-md border border-white/10 px-3 py-2 text-xs text-slate-300">
                voice clone {plan.voice_clone_enabled ? "on" : "off"}
              </span>
            </div>
            <AdminPlanForm plan={plan} />
          </article>
        ))}
        {plans.length === 0 && !error ? <p className="rounded-lg border border-white/10 bg-panel/80 p-8 text-center text-slate-400">暂无套餐。</p> : null}
      </section>
    </main>
  );
}
