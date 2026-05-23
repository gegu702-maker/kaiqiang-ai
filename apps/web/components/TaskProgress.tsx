import type { TaskStatus } from "@/lib/types";

const progressByStatus: Record<TaskStatus, number> = {
  pending: 18,
  scripting: 38,
  producing: 68,
  processing: 62,
  completed: 100,
  failed: 100,
};

const labelByStatus: Record<TaskStatus, string> = {
  pending: "等待管理员处理",
  scripting: "AI 脚本和分镜已生成",
  producing: "管理员正在制作视频",
  processing: "视频生成处理中",
  completed: "视频已完成",
  failed: "任务处理失败",
};

export function TaskProgress({ status }: { status: TaskStatus }) {
  const value = progressByStatus[status];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-300">{labelByStatus[status]}</span>
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
