"use client";

import { useActionState } from "react";
import { Mic2, Trash2 } from "lucide-react";

import { deleteVoiceCloneAction, uploadVoiceCloneAction } from "@/app/actions/voiceClone";
import { SubmitButton } from "@/components/SubmitButton";
import type { VoiceClone } from "@/lib/types";

const initialState = { ok: false, message: "" };

export function VoiceCloneManager({
  enabled,
  clones,
}: {
  enabled: boolean;
  clones: VoiceClone[];
}) {
  const [uploadState, uploadAction] = useActionState(uploadVoiceCloneAction, initialState);
  const [deleteState, deleteAction] = useActionState(deleteVoiceCloneAction, initialState);

  return (
    <section className="mt-5 rounded-lg border border-white/10 bg-panel/80 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Mic2 className="text-cyan" size={20} />
        <h2 className="text-lg font-semibold text-white">声音克隆管理</h2>
      </div>

      {!enabled ? (
        <p className="rounded-md border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
          当前套餐不支持声音克隆。升级到 Pro 后可上传声音样本，生成专属 voice_id。
        </p>
      ) : (
        <form action={uploadAction} className="grid gap-3 rounded-md border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1.4fr_auto]">
          <input name="name" required placeholder="声音名称，例如：我的带货女声" className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm" />
          <input name="sample_audio" required type="file" accept="audio/mp3,audio/mpeg,audio/x-mpeg,audio/wav,audio/x-wav,audio/m4a,audio/x-m4a,audio/mp4,audio/aac,audio/x-aac,audio/mp4a-latm,video/mp4,.mp3,.wav,.m4a,.mp4,.mpeg" className="h-10 rounded-md border border-white/10 bg-ink/70 text-sm file:h-full file:border-0 file:bg-cyan file:px-3 file:text-ink" />
          <SubmitButton label="创建声音" pendingLabel="创建中" />
          {uploadState.message ? <p className={uploadState.ok ? "text-sm text-lime md:col-span-3" : "text-sm text-rose-200 md:col-span-3"}>{uploadState.message}</p> : null}
        </form>
      )}

      <div className="mt-4 space-y-3">
        {clones.map((clone) => (
          <div key={clone.id} className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium text-white">{clone.name}</p>
                <p className="mt-1 text-slate-400">{clone.provider} · {clone.status}</p>
                <p className="mt-1 break-all text-xs text-cyan">{clone.voice_id || "voice_id 生成中"}</p>
              </div>
              <form action={deleteAction}>
                <input type="hidden" name="voice_clone_id" value={clone.id} />
                <button className="inline-flex items-center gap-1 rounded-md border border-rose-300/30 px-3 py-2 text-xs text-rose-100 hover:bg-rose-400/10">
                  <Trash2 size={14} />
                  删除
                </button>
              </form>
            </div>
          </div>
        ))}
        {deleteState.message ? <p className={deleteState.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{deleteState.message}</p> : null}
        {clones.length === 0 ? <p className="text-sm text-slate-500">暂无专属声音。</p> : null}
      </div>
    </section>
  );
}
