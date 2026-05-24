import Link from "next/link";
import { redirect } from "next/navigation";
import { CreditCard, Gauge, ShieldCheck } from "lucide-react";

import { getUsageSummary } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

export default async function AccountPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/account");
  }

  let usage = null;
  let error = "";
  try {
    usage = await getUsageSummary(session.access_token);
  } catch (err) {
    error = err instanceof Error ? err.message : "额度信息加载失败";
  }

  const plan = usage?.plan ?? "free";
  const remaining = usage?.remaining === null ? "自定义" : `${usage?.remaining ?? 0} 次`;

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <p className="text-sm text-cyan">Account</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">账户与额度</h1>
        <p className="mt-3 text-slate-400">{session.user.email}</p>
      </div>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <div className="grid gap-5 md:grid-cols-3">
        <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
          <ShieldCheck className="text-cyan" size={22} />
          <h2 className="mt-4 text-lg font-semibold text-white">当前套餐</h2>
          <p className="mt-2 text-3xl font-semibold uppercase text-cyan">{plan}</p>
        </section>
        <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
          <Gauge className="text-lime" size={22} />
          <h2 className="mt-4 text-lg font-semibold text-white">本月剩余额度</h2>
          <p className="mt-2 text-3xl font-semibold text-lime">{remaining}</p>
        </section>
        <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
          <CreditCard className="text-cyan" size={22} />
          <h2 className="mt-4 text-lg font-semibold text-white">支付状态</h2>
          <p className="mt-2 text-sm text-slate-400">真实支付未启用，订单和 provider 层已预留。</p>
        </section>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="rounded-md bg-cyan px-5 py-3 text-sm font-semibold text-ink hover:bg-cyan/90" href="/pricing">
          查看套餐
        </Link>
        <Link className="rounded-md border border-white/10 px-5 py-3 text-sm text-slate-200 hover:bg-white/10" href="/tasks">
          我的任务
        </Link>
      </div>
    </main>
  );
}
