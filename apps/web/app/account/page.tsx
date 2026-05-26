import Link from "next/link";
import { redirect } from "next/navigation";
import { CreditCard, Download, Gauge, KeyRound, ReceiptText, ShieldCheck } from "lucide-react";

import { getUserOrders, getUserTasks, getUserUsageLogs, getUsageSummary } from "@/lib/api";
import { getVoiceClones } from "@/lib/api";
import { TrackedDownloadLink } from "@/components/TrackedDownloadLink";
import { VoiceCloneManager } from "@/components/VoiceCloneManager";
import { createClient } from "@/lib/supabase/server";
import type { Order, UsageLog, UsageSummary, VideoTask, VoiceClone } from "@/lib/types";

const FREE_USAGE_FALLBACK: UsageSummary = {
  plan: "free",
  monthly_quota: 3,
  used: 0,
  remaining: 3,
  period_start: new Date().toISOString(),
  voice_clone_enabled: false,
  default_voice_id: null,
};

export default async function AccountPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/account");
  }

  let usage: UsageSummary = FREE_USAGE_FALLBACK;
  let orders: Order[] = [];
  let usageLogs: UsageLog[] = [];
  let tasks: VideoTask[] = [];
  let voiceClones: VoiceClone[] = [];
  let error = "";
  try {
    usage = (await getUsageSummary(session.access_token)) ?? FREE_USAGE_FALLBACK;
  } catch (err) {
    console.error("[AccountPage] usage fallback", err);
    error = "额度初始化中，已按 Free 套餐默认显示。刷新后会自动同步。";
  }
  try {
    orders = await getUserOrders(session.access_token);
  } catch (err) {
    console.error("[AccountPage] orders failed", err);
  }
  try {
    usageLogs = await getUserUsageLogs(session.access_token);
  } catch (err) {
    console.error("[AccountPage] usage logs failed", err);
  }
  try {
    tasks = await getUserTasks(session.access_token);
  } catch (err) {
    console.error("[AccountPage] tasks failed", err);
  }
  try {
    voiceClones = await getVoiceClones(session.access_token);
  } catch (err) {
    console.error("[AccountPage] voice clones failed", err);
  }

  const plan = usage.plan;
  const remaining = usage.remaining === null ? "自定义" : `${usage.remaining} 次`;

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

      <div className="mt-8 grid gap-5 lg:grid-cols-2">
        <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
          <div className="mb-4 flex items-center gap-2">
            <ReceiptText className="text-cyan" size={20} />
            <h2 className="text-lg font-semibold text-white">我的订单</h2>
          </div>
          <div className="space-y-3">
            {orders.slice(0, 6).map((order) => (
              <div key={order.id} className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-white">{order.plan.toUpperCase()} · {order.billing_cycle}</span>
                  <span className="rounded-full border border-white/10 px-2 py-1 text-xs text-slate-300">{order.status}</span>
                </div>
                <p className="mt-2 text-slate-400">{order.currency} {(order.amount / 100).toFixed(2)} · {order.provider}</p>
              </div>
            ))}
            {orders.length === 0 ? <p className="text-sm text-slate-500">暂无订单。</p> : null}
          </div>
        </section>

        <section className="rounded-lg border border-white/10 bg-panel/80 p-5">
          <div className="mb-4 flex items-center gap-2">
            <Gauge className="text-lime" size={20} />
            <h2 className="text-lg font-semibold text-white">消费记录</h2>
          </div>
          <div className="space-y-3">
            {usageLogs.slice(0, 6).map((log) => (
              <div key={log.id} className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-white">{log.action}</span>
                  <span className="text-slate-400">-{log.quantity}</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</p>
              </div>
            ))}
            {usageLogs.length === 0 ? <p className="text-sm text-slate-500">暂无消耗记录。</p> : null}
          </div>
        </section>
      </div>

      <section className="mt-5 rounded-lg border border-white/10 bg-panel/80 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Download className="text-cyan" size={20} />
          <h2 className="text-lg font-semibold text-white">可下载视频</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {tasks
            .filter((task) => task.result_video_url)
            .slice(0, 6)
            .map((task) => (
              <TrackedDownloadLink
                key={task.id}
                href={task.result_video_url ?? "#"}
                target="_blank"
                rel="noreferrer"
                download
                taskId={task.id}
                productName={task.product_name}
                className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-300 hover:border-cyan/40 hover:text-cyan"
              >
                {task.product_name}
              </TrackedDownloadLink>
            ))}
          {tasks.filter((task) => task.result_video_url).length === 0 ? (
            <p className="text-sm text-slate-500">暂无已完成视频。</p>
          ) : null}
        </div>
      </section>

      <section className="mt-5 rounded-lg border border-white/10 bg-white/[0.04] p-5">
        <div className="flex items-center gap-2">
          <KeyRound className="text-cyan" size={20} />
          <h2 className="text-lg font-semibold text-white">API Key（预留）</h2>
        </div>
        <p className="mt-2 text-sm text-slate-400">API Key 数据表和权限已预留，后续开放开放平台时可直接接入。</p>
      </section>

      <VoiceCloneManager enabled={Boolean(usage.voice_clone_enabled)} clones={voiceClones} />
    </main>
  );
}
