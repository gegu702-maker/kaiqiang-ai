import type { ReactNode } from "react";
import {
  Captions,
  ClipboardList,
  Film,
  Hash,
  Lightbulb,
  ListChecks,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

import { CopyButton } from "@/components/CopyButton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ShotItem, VideoTask } from "@/lib/types";

const styleLabels: Record<string, string> = {
  hard_sell: "硬核带货",
  emotional_seed: "情绪种草",
  review: "测评解说",
  story: "剧情短片",
};

export function CommerceAiOutput({ task }: { task: VideoTask }) {
  const sellingPoints = task.selling_points || [];
  const shots = task.shot_list || [];
  const titles = task.title_options || [];
  const hashtags = task.hashtags || [];
  const workflow = task.admin_workflow || [];
  const shotText = formatShotList(shots);
  const workflowText = workflow.map((item) => `${item.step}. [${item.tool}] ${item.action}`).join("\n");
  const promptText = shots
    .map((shot) => `镜头 ${shot.index}｜${shot.tool_suggestion}\n${shot.visual_prompt}`)
    .join("\n\n");

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles size={17} />
            AI Video Agent 生成结果
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Info label="视频风格" value={styleLabels[task.video_style] || task.video_style || "未填写"} />
          <Info label="目标人群" value={task.target_audience || "未填写"} />
          <Info label="生产模式" value={task.production_mode || "semi_auto"} />
          <Info label="数字人" value={task.use_digital_human ? "使用数字人" : "不使用数字人"} />
        </CardContent>
      </Card>

      <WorkflowStatus />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <Lightbulb size={17} />
              AI 卖点分析
            </CardTitle>
            <CopyButton value={JSON.stringify(sellingPoints, null, 2)} label="复制卖点" />
          </div>
        </CardHeader>
        <CardContent className="grid gap-3">
          {sellingPoints.map((item) => (
            <div key={item.index} className="rounded-lg border border-white/10 bg-white/[0.04] p-4 transition hover:border-cyan/25 hover:bg-cyan/[0.05]">
              <p className="text-sm font-semibold text-white">{item.index}. {item.point}</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.consumer_benefit}</p>
              <p className="mt-2 text-xs text-cyan">{item.proof_angle}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <MessageSquareText size={17} />
              AI 脚本与标题
            </CardTitle>
            <div className="flex flex-wrap gap-2">
              <CopyButton value={task.hook} label="复制开头" />
              <CopyButton value={task.script} label="复制脚本" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-cyan/20 bg-cyan/5 p-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-cyan">黄金 3 秒开头</p>
            <p className="text-lg font-semibold leading-7 text-white">{task.hook}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{task.script}</p>
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-200">视频标题</p>
              <CopyButton value={titles.join("\n")} label="复制标题" />
            </div>
            {titles.map((title) => (
              <p key={title} className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
                {title}
              </p>
            ))}
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-200">Caption</p>
              <CopyButton value={task.caption} label="复制 caption" />
            </div>
            <p className="text-sm text-slate-400">{task.caption}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <Hash size={17} />
              抖音带货增长模块
            </CardTitle>
            <CopyButton
              value={[
                `封面文案：${task.cover_text}`,
                `封面Prompt：${task.cover_prompt}`,
                `标签：${hashtags.join(" ")}`,
                task.comment_prompt,
                task.closing_cta,
              ].join("\n")}
              label="复制增长包"
            />
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-2">
          <CommercialBlock icon={<Captions size={16} />} label="AI封面文案" value={task.cover_text} copyLabel="复制封面" />
          <CommercialBlock icon={<Film size={16} />} label="AI封面生成 prompt" value={task.cover_prompt} copyLabel="复制prompt" />
          <CommercialBlock icon={<Hash size={16} />} label="AI标签" value={hashtags.join(" ")} copyLabel="复制标签" />
          <CommercialBlock icon={<MessageSquareText size={16} />} label="评论区引导" value={task.comment_prompt} copyLabel="复制评论" />
          <div className="lg:col-span-2">
            <CommercialBlock icon={<Sparkles size={16} />} label="成交收口" value={task.closing_cta} copyLabel="复制收口" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <Film size={17} />
              可视化 AI Storyboard
            </CardTitle>
            <div className="flex flex-wrap gap-2">
              <CopyButton value={shotText} label="复制分镜" />
              <CopyButton value={promptText} label="复制提示词" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {shots.map((shot, index) => (
            <ShotCard key={shot.index} shot={shot} isLast={index === shots.length - 1} />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <ClipboardList size={17} />
              HeyGen / 即梦 / 可灵执行清单
            </CardTitle>
            <CopyButton value={workflowText} label="复制清单" />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {workflow.map((item) => (
            <div key={item.step} className="rounded-lg border border-white/10 bg-white/[0.04] p-4 transition hover:border-cyan/25">
              <p className="text-sm font-semibold text-white">
                Step {item.step} · {item.tool}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.action}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function WorkflowStatus() {
  const steps = [
    ["AI卖点分析", "done"],
    ["AI脚本生成", "done"],
    ["AI分镜生成", "done"],
    ["AI视觉Prompt", "done"],
    ["数字人口播", "active"],
    ["视频剪辑", "next"],
    ["字幕合成", "next"],
    ["视频导出", "next"],
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles size={17} />
          AI 生产管线
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4 h-2 overflow-hidden rounded-full bg-white/10">
          <div className="h-full w-[58%] rounded-full bg-gradient-to-r from-cyan via-lime to-cyan" />
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          {steps.map(([label, status]) => (
            <div key={label} className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
              <span className={status === "done" ? "size-2 rounded-full bg-lime" : status === "active" ? "size-2 animate-pulse rounded-full bg-cyan" : "size-2 rounded-full bg-slate-600"} />
              <span className={status === "next" ? "text-sm text-slate-500" : "text-sm text-slate-200"}>{label}</span>
              {status === "active" ? <span className="ml-auto text-xs text-cyan">生成中</span> : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CommercialBlock({
  icon,
  label,
  value,
  copyLabel,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  copyLabel: string;
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-xs font-medium text-cyan">
          {icon}
          {label}
        </p>
        <CopyButton value={value} label={copyLabel} />
      </div>
      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-300">{value}</p>
    </div>
  );
}

function ShotCard({ shot, isLast }: { shot: ShotItem; isLast: boolean }) {
  return (
    <div className="relative pl-8">
      {!isLast ? <div className="absolute left-[11px] top-8 h-[calc(100%-6px)] w-px bg-gradient-to-b from-cyan/50 to-white/10" /> : null}
      <div className="absolute left-0 top-5 grid size-6 place-items-center rounded-full border border-cyan/40 bg-cyan/15 text-[11px] font-semibold text-cyan">
        {shot.index}
      </div>
      <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.04] transition hover:border-cyan/25 hover:bg-cyan/[0.045]">
        <div className="grid gap-0 lg:grid-cols-[210px_1fr]">
          <div className="relative min-h-[190px] border-b border-white/10 bg-[linear-gradient(145deg,#07111f,#112231_45%,#1a2016)] p-4 lg:border-b-0 lg:border-r">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_10%,rgba(49,215,255,0.25),transparent_34%)]" />
            <div className="relative flex h-full flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="rounded-full border border-white/15 bg-black/30 px-2 py-1 text-xs text-slate-300">{shot.duration}</span>
                <span className="rounded-full border border-cyan/25 bg-cyan/10 px-2 py-1 text-xs text-cyan">{shot.tool_suggestion}</span>
              </div>
              <div className="space-y-3">
                <div className="mx-auto h-20 w-24 rounded-2xl border border-white/15 bg-white/10 shadow-glow" />
                <div className="rounded-lg bg-black/45 px-3 py-2 text-center text-xs font-semibold leading-5 text-white">
                  {shot.scene}
                </div>
              </div>
            </div>
          </div>
          <div className="p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold text-white">
                镜头 {shot.index} · {shot.scene}
              </p>
              <span className="text-xs text-slate-500">AI preview</span>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-2">
              <Info label="运镜" value={shot.camera} />
              <Info label="动作" value={shot.action} />
              <Info label="旁白" value={shot.narration} />
              <Info label="平台标签" value={shot.tool_suggestion} />
            </div>
            <div className="mt-3 rounded-md border border-white/10 bg-ink/60 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-xs font-medium text-slate-400">
                  <ListChecks size={14} />
                  visual prompt
                </p>
                <CopyButton value={shot.visual_prompt} label="复制" />
              </div>
              <p className="text-sm leading-6 text-slate-300">{shot.visual_prompt}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm leading-6 text-slate-200">{value}</p>
    </div>
  );
}

function formatShotList(shots: ShotItem[]) {
  return shots
    .map(
      (shot) =>
        `镜头 ${shot.index}（${shot.duration}）\n场景：${shot.scene}\n镜头：${shot.camera}\n动作：${shot.action}\n旁白：${shot.narration}\n提示词：${shot.visual_prompt}\n工具：${shot.tool_suggestion}`,
    )
    .join("\n\n");
}
