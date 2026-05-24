import { clsx } from "clsx";

import type { TaskStatus } from "@/lib/types";

const styles: Record<TaskStatus, string> = {
  waiting: "border-amber-300/30 bg-amber-300/10 text-amber-200",
  generating_script: "border-fuchsia-300/30 bg-fuchsia-300/10 text-fuchsia-100",
  cloning_voice: "border-purple-300/30 bg-purple-300/10 text-purple-100",
  generating_voice: "border-blue-300/30 bg-blue-300/10 text-blue-100",
  generating_avatar: "border-violet-300/30 bg-violet-300/10 text-violet-100",
  rendering: "border-cyan/30 bg-cyan/10 text-cyan",
  success: "border-lime/30 bg-lime/10 text-lime",
  pending: "border-amber-300/30 bg-amber-300/10 text-amber-200",
  scripting: "border-fuchsia-300/30 bg-fuchsia-300/10 text-fuchsia-100",
  producing: "border-cyan/30 bg-cyan/10 text-cyan",
  processing: "border-cyan/30 bg-cyan/10 text-cyan",
  completed: "border-lime/30 bg-lime/10 text-lime",
  failed: "border-rose-300/30 bg-rose-400/10 text-rose-200",
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
  <span className={clsx("rounded-full border px-2.5 py-1 text-xs font-medium", styles[status] ?? styles.pending)}>
      {status}
    </span>
  );
}
