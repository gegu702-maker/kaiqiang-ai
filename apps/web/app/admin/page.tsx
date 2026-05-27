import Image from "next/image";
import Link from "next/link";
import { ExternalLink, WandSparkles } from "lucide-react";

import { AdminUpdateForm } from "@/components/AdminUpdateForm";
import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { getAdminTasks } from "@/lib/api";
import { getAvatarProfile } from "@/lib/avatars";
import { getLanguageLabel, getTTSVoiceLabel } from "@/lib/tts";
import type { VideoTask } from "@/lib/types";

export default async function AdminPage() {
  let tasks: VideoTask[] = [];
  let error = "";

  try {
    tasks = await getAdminTasks();
  } catch (err) {
    error = err instanceof Error ? err.message : "管理员任务加载失败";
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">管理后台</h1>
          <p className="mt-2 text-slate-400">查看任务、调整状态、上传最终 MP4 视频。</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-300">
          共 {tasks.length} 个任务
        </div>
        <Button asChild variant="outline">
          <Link href="/admin/billing">商业化后台</Link>
        </Button>
      </div>

      {error ? <p className="rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <div className="overflow-hidden rounded-lg border border-white/10 bg-panel/80 shadow-glow">
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
