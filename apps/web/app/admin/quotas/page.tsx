import Link from "next/link";
import { ArrowLeft, CreditCard, Gauge, UsersRound } from "lucide-react";

import { AdminQuotaForm } from "@/components/AdminCommercialForms";
import { Button } from "@/components/ui/button";
import { getAdminQuotas } from "@/lib/api";
import { requireAdmin } from "@/lib/adminAuth";
import type { AdminQuota } from "@/lib/types";

export default async function AdminQuotasPage() {
  await requireAdmin("/admin/quotas");

  let quotas: AdminQuota[] = [];
  let error = "";

  try {
    quotas = await getAdminQuotas();
  } catch (err) {
    error = err instanceof Error ? err.message : "额度数据加载失败";
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
          <Link href="/admin/plans">
            <CreditCard size={16} />
            套餐管理
          </Link>
        </Button>
      </div>

      <div className="mb-6">
        <p className="text-sm text-cyan">Quotas</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">额度管理</h1>
        <p className="mt-2 text-slate-400">查看并修正当前月份用户额度，不触发生成任务重跑。</p>
      </div>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <section className="overflow-hidden rounded-lg border border-white/10 bg-panel/80">
        <div className="grid gap-3 border-b border-white/10 px-4 py-3 text-xs uppercase tracking-wide text-slate-500 md:grid-cols-[1fr_110px_120px_120px_auto]">
          <span>用户</span>
          <span>月额度</span>
          <span>已用</span>
          <span>剩余</span>
          <span>操作</span>
        </div>
        <div className="divide-y divide-white/10">
          {quotas.map((quota) => (
            <article key={quota.id} className="p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm">
                <div className="flex min-w-0 items-center gap-2">
                  <Gauge className="shrink-0 text-cyan" size={18} />
                  <span className="break-all text-white">{quota.email || quota.user_id}</span>
                  <span className="rounded-full border border-white/10 px-2 py-1 text-xs text-slate-400">{quota.plan}</span>
                </div>
                <span className="text-xs text-slate-500">reset {quota.reset_month}</span>
              </div>
              <AdminQuotaForm quota={quota} />
            </article>
          ))}
          {quotas.length === 0 && !error ? <p className="p-8 text-center text-slate-400">暂无额度记录。</p> : null}
        </div>
      </section>
    </main>
  );
}
