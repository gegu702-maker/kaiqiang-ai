import Link from "next/link";
import { redirect } from "next/navigation";

import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { TaskCard } from "@/components/TaskCard";
import { getUserTasks } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import type { VideoTask } from "@/lib/types";

export default async function TasksPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/tasks");
  }

  let tasks: VideoTask[] = [];
  let error = "";

  try {
    tasks = await getUserTasks(session.access_token);
  } catch (err) {
    error = err instanceof Error ? err.message : "任务加载失败";
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6">
        <h1 className="text-3xl font-semibold text-white">我的任务</h1>
        <p className="mt-2 text-slate-400">当前账户：{session.user.email}。这里只展示你自己的视频任务。</p>
      </div>

      {error ? <p className="rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <div className="space-y-4">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
        {tasks.length === 0 && !error ? (
          <p className="rounded-lg border border-white/10 bg-white/[0.04] p-6 text-center text-slate-400">
            还没有任务。<Link href="/" className="text-cyan hover:text-cyan/80">去生成第一个 AI 带货视频方案</Link>
          </p>
        ) : null}
      </div>
    </main>
  );
}
