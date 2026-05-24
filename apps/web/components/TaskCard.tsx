import Image from "next/image";
import Link from "next/link";
import { Download, FileAudio2, UserRound } from "lucide-react";

import { StatusBadge } from "@/components/StatusBadge";
import { getAvatarProfile } from "@/lib/avatars";
import { getLanguageLabel, getTTSVoiceLabel } from "@/lib/tts";
import type { VideoTask } from "@/lib/types";

export function TaskCard({ task }: { task: VideoTask }) {
  const avatar = getAvatarProfile(task.avatar_id);

  return (
    <article className="grid gap-4 rounded-lg border border-white/10 bg-panel/80 p-4 shadow-glow sm:grid-cols-[112px_1fr]">
      <div className="relative aspect-square overflow-hidden rounded-md border border-white/10 bg-white/5">
        <Image src={task.image_url} alt={task.product_name} fill className="object-cover" />
      </div>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link href={`/tasks/${task.id}`} className="text-lg font-semibold text-white hover:text-cyan">
              {task.product_name}
            </Link>
            <p className="text-sm text-slate-400">{new Date(task.created_at).toLocaleString()}</p>
          </div>
          <StatusBadge status={task.status} />
        </div>
        <p className="line-clamp-3 text-sm leading-6 text-slate-300">{task.script}</p>
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
          <span>语言：{getLanguageLabel(task.tts_language || task.language)}</span>
          <span>Voice：{getTTSVoiceLabel(task.tts_voice_name)}</span>
          <span className="inline-flex items-center gap-1.5">
            <UserRound size={14} />
            主播：{avatar.name}
          </span>
          <a
            className="inline-flex items-center gap-1.5 text-cyan hover:text-cyan/80"
            href={task.voice_url}
            target="_blank"
            rel="noreferrer"
          >
            <FileAudio2 size={14} />
            声音素材
          </a>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3 text-sm text-slate-400">
          {(task.status === "completed" || task.status === "success") && task.result_video_url ? (
            <a
              className="inline-flex items-center gap-2 rounded-md border border-lime/30 px-3 py-2 text-lime hover:bg-lime/10"
              href={task.result_video_url}
              target="_blank"
              rel="noreferrer"
            >
              <Download size={16} />
              下载视频
            </a>
          ) : null}
        </div>
      </div>
    </article>
  );
}
