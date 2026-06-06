import Link from "next/link";
import { ArrowLeft, Ban, CreditCard, UserCog } from "lucide-react";

import { AdminUserForm } from "@/components/AdminBillingForms";
import { Button } from "@/components/ui/button";
import { getAdminUsers } from "@/lib/api";
import { requireAdmin } from "@/lib/adminAuth";
import type { AdminUser } from "@/lib/types";

export default async function AdminUsersPage() {
  await requireAdmin("/admin/users");

  let users: AdminUser[] = [];
  let error = "";

  try {
    users = await getAdminUsers();
  } catch (err) {
    error = err instanceof Error ? err.message : "用户数据加载失败";
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
          <Link href="/admin/plans">
            <CreditCard size={16} />
            套餐管理
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/admin/quotas">额度管理</Link>
        </Button>
      </div>

      <div className="mb-6">
        <p className="text-sm text-cyan">Users</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">用户管理</h1>
        <p className="mt-2 text-slate-400">管理套餐、封禁状态、自定义额度和声音克隆权限。</p>
      </div>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <section className="overflow-hidden rounded-lg border border-white/10 bg-panel/80">
        <div className="grid gap-3 border-b border-white/10 px-4 py-3 text-xs uppercase tracking-wide text-slate-500 lg:grid-cols-[1fr_110px_120px_120px_130px_auto]">
          <span>用户</span>
          <span>套餐</span>
          <span>自定义额度</span>
          <span>状态</span>
          <span>声音克隆</span>
          <span>操作</span>
        </div>
        <div className="divide-y divide-white/10">
          {users.map((user) => (
            <article key={user.id} className="p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm">
                <div className="flex min-w-0 items-center gap-2">
                  <UserCog className="shrink-0 text-cyan" size={18} />
                  <span className="break-all text-white">{user.email}</span>
                  <span className="break-all text-xs text-slate-500">{user.id}</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-cyan/20 bg-cyan/10 px-2 py-1 text-xs text-cyan">
                    voice clones {user.voice_clone_count ?? 0}
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
            </article>
          ))}
          {users.length === 0 && !error ? <p className="p-8 text-center text-slate-400">暂无用户。</p> : null}
        </div>
      </section>
    </main>
  );
}
