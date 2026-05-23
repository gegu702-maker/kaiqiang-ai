import { Search } from "lucide-react";

import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { TaskCard } from "@/components/TaskCard";
import { getUserTasks } from "@/lib/api";
import type { VideoTask } from "@/lib/types";

type Props = {
  searchParams: Promise<{ email?: string }>;
};

export default async function TasksPage({ searchParams }: Props) {
  const { email = "" } = await searchParams;
  let tasks: VideoTask[] = [];
  let error = "";

  try {
    tasks = await getUserTasks(email);
  } catch (err) {
    error = err instanceof Error ? err.message : "任务加载失败";
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6">
        <h1 className="text-3xl font-semibold text-white">我的任务</h1>
        <p className="mt-2 text-slate-400">输入提交任务时使用的邮箱，查看状态并下载已完成视频。</p>
      </div>

      <form className="mb-8 flex flex-col gap-3 rounded-lg border border-white/10 bg-panel/80 p-4 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input
            name="email"
            type="email"
            defaultValue={email}
            placeholder="you@company.com"
            className="h-11 w-full rounded-md border border-white/10 bg-white/5 pl-10 pr-3 outline-none ring-cyan/40 placeholder:text-slate-500 focus:ring-2"
          />
        </div>
        <button className="h-11 rounded-md bg-cyan px-5 text-sm font-semibold text-ink hover:bg-cyan/90">
          查询
        </button>
      </form>

      {error ? <p className="rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p> : null}

      <div className="space-y-4">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
        {email && tasks.length === 0 && !error ? (
          <p className="rounded-lg border border-white/10 bg-white/[0.04] p-6 text-center text-slate-400">
            还没有找到任务。
          </p>
        ) : null}
      </div>
    </main>
  );
}
