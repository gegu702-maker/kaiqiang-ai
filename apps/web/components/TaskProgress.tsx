import type { TaskStatus } from "@/lib/types";

const progressByStatus: Record<TaskStatus, number> = {
  waiting: 16,
  generating_script: 32,
  cloning_voice: 42,
  generating_voice: 48,
  generating_avatar: 62,
  rendering: 72,
  success: 100,
  pending: 18,
  scripting: 38,
  producing: 68,
  processing: 62,
  completed: 100,
  failed: 100,
};

const labelByStatus: Record<TaskStatus, string> = {
  waiting: "任务已进入队列",
  generating_script: "GPT 正在生成脚本",
  cloning_voice: "正在准备克隆声音",
  generating_voice: "TTS 正在生成配音",
  generating_avatar: "数字人口播处理中",
  rendering: "视频工作流生成中",
  success: "视频已完成",
  pending: "等待管理员处理",
  scripting: "AI 脚本和分镜已生成",
  producing: "管理员正在制作视频",
  processing: "视频生成处理中",
  completed: "视频已完成",
  failed: "任务处理失败",
};

export function TaskProgress({ status }: { status: TaskStatus }) {
  const value = progressByStatus[status] ?? 18;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-300">{labelByStatus[status] ?? "任务处理中"}</span>
        <span className={status === "failed" ? "text-rose-200" : "text-cyan"}>{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className={status === "failed" ? "h-full rounded-full bg-rose-300" : "h-full rounded-full bg-cyan"}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
