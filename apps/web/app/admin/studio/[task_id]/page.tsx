import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, Download, ExternalLink, FileAudio2, ImageIcon, Languages, Link2, Sparkles, UserRound } from "lucide-react";

import { CopyButton } from "@/components/CopyButton";
import { CommerceAiOutput } from "@/components/CommerceAiOutput";
import { HeyGenProductionForm } from "@/components/HeyGenProductionForm";
import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { StatusBadge } from "@/components/StatusBadge";
import { StudioUploadForm } from "@/components/StudioUploadForm";
import { VideoPlayer } from "@/components/VideoPlayer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAdminTask } from "@/lib/api";
import { getAvatarProfile } from "@/lib/avatars";
import { getLanguageLabel, getTTSVoiceLabel } from "@/lib/tts";
import type { VideoTask } from "@/lib/types";

type Props = {
  params: Promise<{ task_id: string }>;
};

const studioTools = [
  {
    name: "HeyGen",
    url: "https://app.heygen.com/",
    purpose: "使用用户形象素材、参考语音和文案，生成 avatar 口播视频。",
  },
  {
    name: "剪映",
    url: "https://www.jianying.com/web",
    purpose: "合成字幕、配乐、贴纸、商品卖点和成片包装。",
  },
  {
    name: "CapCut",
    url: "https://www.capcut.com",
    purpose: "国际版剪辑包装、字幕和短视频平台格式导出。",
  },
];

export default async function AdminStudioPage({ params }: Props) {
  const { task_id } = await params;
  let task: VideoTask | null = null;
  let error = "";

  try {
    task = await getAdminTask(task_id);
  } catch (err) {
    error = err instanceof Error ? err.message : "任务加载失败";
  }

  if (!task) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Button asChild variant="ghost">
          <Link href="/admin">
            <ArrowLeft size={16} />
            返回管理后台
          </Link>
        </Button>
        <p className="mt-6 rounded-lg border border-rose-300/20 bg-rose-400/10 p-4 text-rose-100">{error}</p>
      </main>
    );
  }

  const avatar = getAvatarProfile(task.avatar_id);
  const languageLabel = getLanguageLabel(task.tts_language || task.language);
  const voiceLabel = getTTSVoiceLabel(task.tts_voice_name);
  const personalImageUrl = task.personal_image_url || task.image_url;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-3 mb-3">
            <Link href={`/admin/tasks/${task.id}`}>
              <ArrowLeft size={16} />
              返回任务详情
            </Link>
          </Button>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-white">AI 视频生成工作台</h1>
            <StatusBadge status={task.status} />
          </div>
          <p className="mt-2 text-sm text-slate-500">{task.product_name} · 半自动视频生产流程</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <CopyButton value={task.script} label="Copy Script" />
          <Button asChild variant="outline" size="sm">
            <a href={task.voice_url} target="_blank" rel="noreferrer" download>
              <Download size={15} />
              Download Voice
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={task.image_url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} />
              Open Product Image
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={personalImageUrl} target="_blank" rel="noreferrer" download>
              <Download size={15} />
              Download Persona
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href="https://app.heygen.com/" target="_blank" rel="noreferrer">
              <ExternalLink size={15} />
              Open HeyGen
            </a>
          </Button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>任务信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Product</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">{task.product_name}</h2>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <InfoPill icon={<Languages size={16} />} label="当前语言" value={languageLabel} />
                <InfoPill icon={<FileAudio2 size={16} />} label="参考 voice" value={voiceLabel} />
                <InfoPill icon={<UserRound size={16} />} label="形象来源" value={`${avatar.name} · ${avatar.label}`} />
                <InfoPill icon={<FileAudio2 size={16} />} label="字幕状态" value={task.subtitle_status} />
                <InfoPill icon={<Sparkles size={16} />} label="生产模式" value="HeyGen 半自动" />
                <InfoPill icon={<Link2 size={16} />} label="HeyGen video_id" value={task.heygen_video_id || "未填写"} />
                <InfoPill icon={<Sparkles size={16} />} label="队列状态" value={task.queue_status || "未入队"} />
                <InfoPill icon={<Sparkles size={16} />} label="队列尝试次数" value={`${task.queue_attempts ?? 0}/3`} />
              </div>

              <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium text-slate-200">视频文案</h3>
                  <CopyButton value={task.script} label="Copy Script" />
                </div>
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{task.script}</p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-sm text-slate-300">
                    <ImageIcon size={15} />
                    产品图片
                  </div>
                  <a href={task.image_url} target="_blank" rel="noreferrer" className="block">
                    <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-white/10 bg-white/5">
                      <Image src={task.image_url} alt={task.product_name} fill className="object-cover" />
                    </div>
                  </a>
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-2 text-sm text-slate-300">
                    <UserRound size={15} />
                    个人形象素材
                  </div>
                  <a href={personalImageUrl} target="_blank" rel="noreferrer" className="block">
                    <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-white/10 bg-white/5">
                      <Image src={personalImageUrl} alt={`${task.product_name} persona`} fill className="object-cover" />
                    </div>
                  </a>
                </div>
                <div className="md:col-span-2 xl:col-span-1 2xl:col-span-2">
                  <div className="mb-2 flex items-center gap-2 text-sm text-slate-300">
                    <FileAudio2 size={15} />
                    参考语音播放器
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
                    <audio controls src={task.voice_url} className="w-full" />
                    <Button asChild variant="outline" size="sm" className="mt-3">
                      <a href={task.voice_url} target="_blank" rel="noreferrer" download>
                        <Download size={15} />
                        Download Voice
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>视频生成工具区</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {studioTools.map((tool) => (
                <a
                  key={tool.name}
                  href={tool.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-white/10 bg-white/[0.04] p-4 transition hover:border-cyan/40 hover:bg-cyan/5"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-white">{tool.name}</h3>
                    <ExternalLink className="text-cyan" size={16} />
                  </div>
                  <p className="text-sm leading-6 text-slate-400">{tool.purpose}</p>
                </a>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>视频生成步骤提示</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {[
                ["Step 1", "下载参考语音和形象素材"],
                ["Step 2", "打开 HeyGen 并创建 avatar / voice"],
                ["Step 3", "粘贴文案生成视频，记录 HeyGen ID 和 URL"],
                ["Step 4", "上传最终 MP4，交付给用户"],
              ].map(([step, label]) => (
                <div key={step} className="rounded-lg border border-white/10 bg-ink/50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan">{step}</p>
                  <p className="mt-2 text-sm text-slate-200">{label}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <HeyGenProductionForm task={task} />

          <CommerceAiOutput task={task} />

          <StudioUploadForm task={task} />

          {task.heygen_video_url ? (
            <Card>
              <CardHeader>
                <CardTitle>HeyGen 视频 URL</CardTitle>
              </CardHeader>
              <CardContent>
                <Button asChild variant="outline">
                  <a href={task.heygen_video_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    打开 HeyGen 生成结果
                  </a>
                </Button>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>视频预览</CardTitle>
            </CardHeader>
            <CardContent>
              <VideoPlayer url={task.result_video_url} subtitleUrl={task.subtitle_url} script={task.script} />
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}

function InfoPill({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
        {icon}
        {label}
      </div>
      <p className="text-sm font-medium text-slate-100">{value}</p>
    </div>
  );
}
