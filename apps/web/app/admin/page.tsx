import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CalendarClock, ExternalLink, ListChecks, Sparkles, UserCheck, UsersRound, WandSparkles } from "lucide-react";

import { AdminUpdateForm } from "@/components/AdminUpdateForm";
import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { getAdminTasks, getAdminUsers } from "@/lib/api";
import { getAdminStats, isAdminEmail } from "@/lib/admin";
import { getAvatarProfile } from "@/lib/avatars";
import { createClient } from "@/lib/supabase/server";
import { getLanguageLabel, getTTSVoiceLabel } from "@/lib/tts";
import type { AdminStats } from "@/lib/admin";
import type { AdminUser } from "@/lib/types";
import type { VideoTask } from "@/lib/types";

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/admin");
  }
  if (!isAdminEmail(session.user.email)) {
    redirect("/account");
  }

  let tasks: VideoTask[] = [];
  let users: AdminUser[] = [];
  let stats: AdminStats | null = null;
  let error = "";

  try {
    [tasks, users] = await Promise.all([getAdminTasks(), getAdminUsers()]);
    stats = await getAdminStats(users, tasks);
  } catch (err) {
    error = err instanceof Error ? err.message : "管理员数据加载失败";
  }

  const statCards = stats
    ? [
        ["总用户数", stats.totalUsers, UsersRound],
        ["Free 用户数", stats.freeUsers, UserCheck],
        ["Business 用户数", stats.businessUsers, UserCheck],
        ["Waitlist 数量", stats.waitlistCount ?? "需服务密钥", ListChecks],
        ["Avatar 总生成数", stats.avatarGenerations ?? "需服务密钥", Sparkles],
        ["今日生成数", stats.todayGenerations ?? "需服务密钥", CalendarClock],
        ["今日注册数", stats.todayRegistrations, UsersRound],
      ] as const
    : [];

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-cyan">Admin Dashboard</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">只读运营概览</h1>
          <p className="mt-2 text-slate-400">展示用户、等待名单和 Avatar 生成统计，不修改业务逻辑。</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-300">
          共 {tasks.length} 个任务
        </div>
        <Button asChild variant="outline">
          <Link href="/admin/billing">商业化后台</Link>
        </Button>
      </div>

      {error ? <p className="rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      {statCards.length > 0 ? (
        <section className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map(([label, value, Icon]) => (
            <article key={label} className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-slate-400">{label}</p>
                <Icon className="text-cyan" size={20} />
              </div>
              <p className="mt-4 break-words text-3xl font-semibold text-white">{value}</p>
            </article>
          ))}
        </section>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-white/10 bg-panel/80 shadow-glow">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-4">
          <div>
            <h2 className="text-lg font-semibold text-white">任务只读快照</h2>
            <p className="mt-1 text-sm text-slate-500">保留现有任务入口，便于运营排查和跳转详情。</p>
          </div>
        </div>
        <div className="hidden grid-cols-[92px_1.1fr_0.8fr_150px_1.5fr] gap-4 border-b border-white/10 px-4 py-3 text-xs uppercase tracking-wide text-slate-500 lg:grid">
          <span>图片</span>
          <span>任务</span>
          <span>用户</span>
          <span>状态 / 队列</span>
          <span>操作</span>
        </div>
        <div className="divide-y divide-white/10">
          {tasks.map((task) => {
            const avatar = getAvatarProfile(task.avatar_id);
            const outputVideoUrl = task.output_video_url || task.result_video_url;

            return (
              <article key={task.id} className="grid gap-4 p-4 lg:grid-cols-[92px_1.1fr_0.8fr_150px_1.5fr]">
                <div className="relative aspect-square w-24 overflow-hidden rounded-md border border-white/10 bg-white/5 lg:w-auto">
                  <Image src={task.image_url} alt={task.product_name} fill className="object-cover" />
                </div>
                <div className="min-w-0">
                  <Link href={`/admin/tasks/${task.id}`} className="font-semibold text-white hover:text-cyan">
                    {task.product_name}
                  </Link>
                  <p className="mt-1 break-all text-xs text-slate-500">task id: {task.id}</p>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-400">{task.script || task.product_highlights}</p>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">input: {task.product_highlights || task.target_audience || task.script}</p>
                  <p className="mt-2 text-xs text-slate-500">created_at: {new Date(task.created_at).toLocaleString()}</p>
                </div>
                <div className="text-sm text-slate-300">
                  <p>{task.user_email}</p>
                  <p className="mt-2 text-slate-500">{getLanguageLabel(task.tts_language || task.language)}</p>
                  <p className="mt-2 text-slate-400">{getTTSVoiceLabel(task.tts_voice_name)}</p>
                  <p className="mt-2 text-slate-400">{avatar.name}</p>
                  <a className="mt-2 block text-cyan hover:text-cyan/80" href={task.voice_url} target="_blank" rel="noreferrer">
                    声音素材
                  </a>
                </div>
                <div>
                  <div className="space-y-3">
                    <StatusBadge status={task.status} />
                    <div className="space-y-1 text-xs text-slate-400">
                      <p>queue: {task.queue_status || "none"}</p>
                      <p>attempts: {task.queue_attempts ?? 0}/3</p>
                    </div>
                    {outputVideoUrl ? (
                      <Button asChild variant="outline" size="sm">
                        <a href={outputVideoUrl} target="_blank" rel="noreferrer">
                          <ExternalLink size={14} />
                          视频
                        </a>
                      </Button>
                    ) : (
                      <p className="text-xs text-slate-500">output video: none</p>
                    )}
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/admin/tasks/${task.id}`}>
                        <ExternalLink size={14} />
                        详情
                      </Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/admin/studio/${task.id}`}>
                        <WandSparkles size={14} />
                        Studio
                      </Link>
                    </Button>
                  </div>
                </div>
                <AdminUpdateForm task={task} />
              </article>
            );
          })}
          {tasks.length === 0 && !error ? (
            <p className="p-8 text-center text-slate-400">暂无任务。</p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
