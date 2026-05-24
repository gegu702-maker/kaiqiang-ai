import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { StatusBadge } from "@/components/StatusBadge";
import { TaskProgress } from "@/components/TaskProgress";
import { VideoPlayer } from "@/components/VideoPlayer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTask } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { VideoTask } from "@/lib/types";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function UserTaskDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect(`/login?next=/tasks/${id}`);
  }

  let task: VideoTask | null = null;
  let error = "";

  try {
    task = await getTask(id, session.access_token);
  } catch (err) {
    error = err instanceof Error ? err.message : "任务加载失败";
  }

  if (!task) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Button asChild variant="ghost">
          <Link href="/tasks">
            <ArrowLeft size={16} />
            返回我的任务
          </Link>
        </Button>
        <p className="mt-6 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-5">
        <Link href="/tasks">
          <ArrowLeft size={16} />
          返回任务列表
        </Link>
      </Button>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-white">{task.product_name}</h1>
            <StatusBadge status={task.status} />
          </div>
          <p className="mt-2 text-sm text-slate-500">系统每 10 秒自动刷新一次任务状态。</p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>生成进度</CardTitle>
            </CardHeader>
            <CardContent>
              <TaskProgress status={task.status} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>最终视频</CardTitle>
          </CardHeader>
          <CardContent>
            <VideoPlayer
              url={task.result_video_url}
              subtitleUrl={task.subtitle_url}
              script={task.script}
              showSubtitleTools
            />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
