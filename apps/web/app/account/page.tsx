import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight, CreditCard, Download, Gauge, History, KeyRound, LayoutTemplate, ReceiptText, ShieldCheck, Sparkles, UserCircle } from "lucide-react";

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
  const monthlyQuota = usage.monthly_quota ?? null;
  const usedPercent = monthlyQuota && usage.remaining !== null ? Math.min(100, Math.round((usage.used / monthlyQuota) * 100)) : null;
  const avatarUrl = typeof session.user.user_metadata?.avatar_url === "string" ? session.user.user_metadata.avatar_url : "";
  const fullName = typeof session.user.user_metadata?.full_name === "string" ? session.user.user_metadata.full_name : "";
  const completedTasks = tasks.filter((task) => task.result_video_url);
  const quickLinks = [
    { href: "/studio/avatar", label: "Avatar Studio", desc: "上传视频和音频生成数字人口播", icon: Sparkles, primary: true },
    { href: "/pricing", label: "Pricing", desc: "查看套餐和升级选项", icon: CreditCard },
    { href: "/tasks", label: "历史任务", desc: "查看生成记录和下载结果", icon: History },
    { href: "/studio/templates", label: "Templates", desc: "从官方模板开始生成", icon: LayoutTemplate },
  ];

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
      <section className="overflow-hidden rounded-lg border border-white/10 bg-panel/90 shadow-glow">
        <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[1.2fr_0.8fr] lg:p-7">
          <div className="flex min-w-0 flex-col gap-5 sm:flex-row sm:items-center">
            <div className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-full border border-white/10 bg-white/[0.06]">
              {avatarUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={avatarUrl} alt={fullName || session.user.email || "Google avatar"} className="h-full w-full object-cover" referrerPolicy="no-referrer" />
              ) : (
                <UserCircle className="text-slate-400" size={42} />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-cyan">Account Center</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">账户与生成额度</h1>
              <p className="mt-3 truncate text-sm text-slate-400">{fullName ? `${fullName} · ` : ""}{session.user.email}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-xs font-semibold uppercase text-cyan">{plan}</span>
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">Google 登录</span>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm text-slate-400">本月剩余额度</p>
                <p className="mt-2 text-4xl font-semibold text-lime">{remaining}</p>
              </div>
              <Gauge className="text-lime" size={24} />
            </div>
            <div className="mt-4">
              <div className="flex justify-between text-xs text-slate-500">
                <span>已用 {usage.used} 次</span>
                <span>{monthlyQuota ? `共 ${monthlyQuota} 次` : "自定义额度"}</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-lime" style={{ width: `${usedPercent ?? 100}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {error ? <p className="mb-5 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {quickLinks.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={item.primary ? "group rounded-lg border border-cyan/35 bg-cyan/10 p-4 shadow-glow transition hover:-translate-y-0.5 hover:bg-cyan/15" : "group rounded-lg border border-white/10 bg-white/[0.035] p-4 transition hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.06]"}
            >
              <div className="flex items-center justify-between gap-3">
                <span className={item.primary ? "grid size-10 place-items-center rounded-lg bg-cyan text-ink" : "grid size-10 place-items-center rounded-lg bg-white/[0.06] text-cyan"}>
                  <Icon size={19} />
                </span>
                <ArrowRight className="text-slate-500 transition group-hover:translate-x-0.5 group-hover:text-cyan" size={17} />
              </div>
              <h2 className="mt-4 text-base font-semibold text-white">{item.label}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.desc}</p>
            </Link>
          );
        })}
      </div>

      <div className="mt-5 grid gap-5 md:grid-cols-3">
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
          <p className="mt-2 text-sm text-slate-400">{orders.length > 0 ? `${orders.length} 个订单记录` : "暂无订单记录"}</p>
        </section>
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
          {completedTasks
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
          {completedTasks.length === 0 ? (
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
