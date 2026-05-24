import Link from "next/link";
import { ArrowLeft, Ban, ReceiptText, UsersRound } from "lucide-react";

import { AdminOrderPaidForm, AdminUserForm } from "@/components/AdminBillingForms";
import { Button } from "@/components/ui/button";
import { getAdminOrders, getAdminUsers } from "@/lib/api";
import type { AdminUser, Order } from "@/lib/types";

export default async function AdminBillingPage() {
  let users: AdminUser[] = [];
  let orders: Order[] = [];
  let error = "";

  try {
    [users, orders] = await Promise.all([getAdminUsers(), getAdminOrders()]);
  } catch (err) {
    error = err instanceof Error ? err.message : "商业化数据加载失败";
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-5">
        <Link href="/admin">
          <ArrowLeft size={16} />
          返回管理后台
        </Link>
      </Button>

      <div className="mb-6">
        <p className="text-sm text-cyan">Commercial Console</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">用户、订单与额度</h1>
        <p className="mt-2 text-slate-400">查看全部用户、支付状态、声音克隆数量，手动调整套餐额度或封禁账户。</p>
      </div>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
        <div className="mb-4 flex items-center gap-2">
          <UsersRound className="text-cyan" size={20} />
          <h2 className="text-xl font-semibold text-white">全部用户</h2>
        </div>
        <div className="space-y-3">
          {users.map((user) => (
            <div key={user.id} className="rounded-md border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-3 text-sm">
                <span className="text-slate-400">{user.id}</span>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-cyan/20 bg-cyan/10 px-2 py-1 text-xs text-cyan">
                    voice clones {user.voice_clone_count ?? 0}
                  </span>
                  <span className={user.voice_clone_enabled ? "rounded-full border border-lime/20 bg-lime/10 px-2 py-1 text-xs text-lime" : "rounded-full border border-white/10 px-2 py-1 text-xs text-slate-400"}>
                    {user.voice_clone_enabled ? "clone enabled" : "clone disabled"}
                  </span>
                  {user.status === "banned" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-rose-300/30 px-2 py-1 text-xs text-rose-200">
                      <Ban size={12} />
                      banned
                    </span>
                  ) : null}
                </div>
              </div>
              <AdminUserForm user={user} />
            </div>
          ))}
          {users.length === 0 ? <p className="text-sm text-slate-500">暂无用户。</p> : null}
        </div>
      </section>

      <section className="mt-6 rounded-lg border border-white/10 bg-panel/80 p-5">
        <div className="mb-4 flex items-center gap-2">
          <ReceiptText className="text-cyan" size={20} />
          <h2 className="text-xl font-semibold text-white">订单</h2>
        </div>
        <div className="space-y-3">
          {orders.map((order) => (
            <div key={order.id} className="rounded-md border border-white/10 bg-white/[0.03] p-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-white">{order.plan.toUpperCase()} · {order.billing_cycle}</p>
                  <p className="mt-1 text-sm text-slate-400">{order.currency} {(order.amount / 100).toFixed(2)} · {order.provider}</p>
                  <p className="mt-1 text-xs text-slate-500">{order.id}</p>
                </div>
                <span className="rounded-full border border-white/10 px-2 py-1 text-xs text-slate-300">{order.status}</span>
              </div>
              {order.status === "pending" ? <div className="mt-3"><AdminOrderPaidForm order={order} /></div> : null}
            </div>
          ))}
          {orders.length === 0 ? <p className="text-sm text-slate-500">暂无订单。</p> : null}
        </div>
      </section>
    </main>
  );
}
