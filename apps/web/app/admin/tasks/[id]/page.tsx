import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, Download, ExternalLink, FileAudio2, Languages, Mail, UserRound, WandSparkles } from "lucide-react";

import { AdminUpdateForm } from "@/components/AdminUpdateForm";
import { AdminTaskRetryForm } from "@/components/AdminTaskRetryForm";
import { CommerceAiOutput } from "@/components/CommerceAiOutput";
import { CopyButton } from "@/components/CopyButton";
import { RefreshOnInterval } from "@/components/RefreshOnInterval";
import { StatusBadge } from "@/components/StatusBadge";
import { TaskProgress } from "@/components/TaskProgress";
import { VideoPlayer } from "@/components/VideoPlayer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAdminTask } from "@/lib/api";
import { getAvatarProfile } from "@/lib/avatars";
import { getLanguageLabel, getTTSVoiceLabel } from "@/lib/tts";
import type { VideoTask } from "@/lib/types";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function AdminTaskDetailPage({ params }: Props) {
  const { id } = await params;
  let task: VideoTask | null = null;
  let error = "";

  try {
    task = await getAdminTask(id);
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

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <RefreshOnInterval seconds={10} />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-3 mb-3">
            <Link href="/admin">
              <ArrowLeft size={16} />
              返回管理后台
            </Link>
          </Button>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-white">{task.product_name}</h1>
            <StatusBadge status={task.status} />
          </div>
          <p className="mt-2 text-sm text-slate-500">任务 ID：{task.id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href={`/admin/studio/${task.id}`}>
              <WandSparkles size={15} />
              打开 AI Studio
            </Link>
          </Button>
          <CopyButton value={task.script} label="复制视频文案" />
          <AdminTaskRetryForm taskId={task.id} />
          <Button asChild variant="outline" size="sm">
            <a href={task.voice_url} target="_blank" rel="noreferrer" download>
              <Download size={15} />
              下载 voice
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={task.image_url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} />
              打开产品图
            </a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={task.personal_image_url || task.image_url} target="_blank" rel="noreferrer" download>
              <Download size={15} />
              下载形象素材
            </a>
          </Button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>用户提交内容</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <InfoItem icon={<Mail size={16} />} label="用户邮箱" value={task.user_email} />
                <InfoItem icon={<Languages size={16} />} label="当前语言" value={getLanguageLabel(task.tts_language || task.language)} />
                <InfoItem icon={<FileAudio2 size={16} />} label="当前 voice" value={getTTSVoiceLabel(task.tts_voice_name)} />
                <InfoItem icon={<FileAudio2 size={16} />} label="voice_type" value={task.tts_voice_name || "未填写"} />
                <InfoItem icon={<FileAudio2 size={16} />} label="字幕状态" value={task.subtitle_status} />
                <InfoItem icon={<UserRound size={16} />} label="形象来源" value={`${avatar.name} · ${avatar.label}`} />
                <InfoItem icon={<UserRound size={16} />} label="avatar_template_id" value={task.avatar_template_id || task.avatar_id} />
                <InfoItem icon={<UserRound size={16} />} label="avatar_template_name" value={task.avatar_template_name || avatar.name} />
                <InfoItem icon={<FileAudio2 size={16} />} label="声音素材" value="mp3 / wav" />
                <InfoItem icon={<WandSparkles size={16} />} label="HeyGen avatar_id" value={task.heygen_avatar_id || "未填写"} />
                <InfoItem icon={<WandSparkles size={16} />} label="HeyGen voice_id" value={task.heygen_voice_id || "未填写"} />
                <InfoItem icon={<WandSparkles size={16} />} label="HeyGen video_id" value={task.heygen_video_id || "未填写"} />
                <InfoItem icon={<WandSparkles size={16} />} label="队列状态" value={task.queue_status || "未入队"} />
                <InfoItem icon={<WandSparkles size={16} />} label="队列尝试次数" value={`${task.queue_attempts ?? 0}/3`} />
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="text-sm font-medium text-slate-200">用户输入卖点</h2>
                  <CopyButton value={task.product_highlights} label="复制" />
                </div>
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{task.product_highlights}</p>
              </div>
            </CardContent>
          </Card>

          <CommerceAiOutput task={task} />

          <Card>
            <CardHeader>
              <CardTitle>处理工作流</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <TaskProgress status={task.status} />
              {task.generation_error ? (
                <div className="rounded-lg border border-rose-300/20 bg-rose-400/10 p-3 text-sm text-rose-100">
                  {task.generation_error}
                </div>
              ) : null}
              <AdminUpdateForm task={task} />
              <p className="text-xs leading-6 text-slate-500">
                管理员可复制 AI 脚本、分镜和提示词，手动粘贴到 HeyGen、即梦、可灵完成视频处理后，在这里上传最终 MP4。
              </p>
            </CardContent>
          </Card>

          {task.heygen_video_url ? (
            <Card>
              <CardHeader>
                <CardTitle>HeyGen 生成结果</CardTitle>
              </CardHeader>
              <CardContent>
                <Button asChild variant="outline">
                  <a href={task.heygen_video_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    打开 HeyGen video_url
                  </a>
                </Button>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>产品图片</CardTitle>
            </CardHeader>
            <CardContent>
              <a href={task.image_url} target="_blank" rel="noreferrer" className="block">
                <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-white/10 bg-white/5">
                  <Image src={task.image_url} alt={task.product_name} fill className="object-cover" />
                </div>
              </a>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>个人形象素材</CardTitle>
            </CardHeader>
            <CardContent>
              <a href={task.personal_image_url || task.image_url} target="_blank" rel="noreferrer" className="block">
                <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-white/10 bg-white/5">
                  <Image src={task.personal_image_url || task.image_url} alt={`${task.product_name} persona`} fill className="object-cover" />
                </div>
              </a>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Voice 音频</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <audio controls src={task.voice_url} className="w-full" />
              <Button asChild variant="outline" size="sm">
                <a href={task.voice_url} target="_blank" rel="noreferrer" download>
                  <Download size={15} />
                  下载声音文件
                </a>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>最终视频</CardTitle>
            </CardHeader>
            <CardContent>
              <VideoPlayer url={task.result_video_url} subtitleUrl={task.subtitle_url} script={task.script} />
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}

function InfoItem({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
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
