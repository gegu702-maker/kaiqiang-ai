"use client";

import { CheckCircle2, Circle, Mic2, PlayCircle, Sparkles, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { ViralAnalyzerClient, type SelectedViralScript, type ViralAnalyzerWorkflowState } from "@/components/ViralAnalyzerClient";

type StepStatus = "completed" | "active" | "pending";

export function StudioWorkspace() {
  const nextStepRef = useRef<HTMLElement | null>(null);
  const [selectedScript, setSelectedScript] = useState<SelectedViralScript | null>(null);
  const [workflowState, setWorkflowState] = useState<ViralAnalyzerWorkflowState>({
    hasLink: false,
    hasAnalysis: false,
    hasRewrites: false,
  });
  const progressSteps = useMemo(
    () => [
      {
        key: "link",
        label: "爆款链接",
        status: workflowState.hasLink || workflowState.hasAnalysis ? "completed" : "active",
      },
      {
        key: "analysis",
        label: "AI拆解",
        status: workflowState.hasAnalysis ? "completed" : workflowState.hasLink ? "active" : "pending",
      },
      {
        key: "script",
        label: "口播文案",
        status: workflowState.hasRewrites ? "completed" : workflowState.hasAnalysis ? "active" : "pending",
      },
      {
        key: "voice",
        label: "声音",
        status: selectedScript ? "active" : "pending",
      },
      {
        key: "video",
        label: "生成视频",
        status: "pending",
      },
    ] satisfies Array<{ key: string; label: string; status: StepStatus }>,
    [selectedScript, workflowState],
  );

  function handleScriptSelect(script: SelectedViralScript) {
    setSelectedScript(script);
    window.setTimeout(() => {
      nextStepRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
  }

  return (
    <main className="min-h-[calc(100vh-86px)] w-full max-w-full overflow-x-hidden bg-ink text-slate-100">
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
        <section className="min-w-0 rounded-lg border border-white/10 bg-panel/85 p-5 shadow-glow">
          <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
            <Sparkles size={15} />
            AI 视频智能体工作台
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">AI 短视频工厂</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
            粘贴爆款视频链接，AI 自动拆解、改写，并衔接声音与数字人口播视频生成。
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-5">
            {progressSteps.map((step, index) => (
              <div
                key={step.key}
                className={[
                  "min-w-0 rounded-md border px-3 py-3",
                  step.status === "completed"
                    ? "border-lime/25 bg-lime/10"
                    : step.status === "active"
                      ? "border-cyan/35 bg-cyan/10"
                      : "border-white/10 bg-white/[0.035]",
                ].join(" ")}
              >
                <p className="text-xs font-semibold text-cyan">0{index + 1}</p>
                <p className="mt-1 truncate text-sm font-semibold text-white">{step.label}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-6 grid w-full max-w-full grid-cols-1 gap-6 overflow-hidden xl:grid-cols-[minmax(0,1fr)_260px]">
          <section className="min-w-0 max-w-full space-y-6 overflow-hidden">
            <ViralAnalyzerClient
              variant="workspace"
              selectedScript={selectedScript}
              onScriptSelect={handleScriptSelect}
              onWorkflowStateChange={setWorkflowState}
            />

            <section ref={nextStepRef} className="min-w-0 max-w-full overflow-hidden rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
              <p className="inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/10 px-3 py-1 text-sm font-semibold text-cyan">
                <Mic2 size={15} />
                下一步：声音与视频生成
              </p>
              {!selectedScript ? (
                <p className="mt-4 text-sm leading-6 text-slate-400">请先选择一条口播文案。选择后可进入声音选择和视频生成准备阶段。</p>
              ) : (
                <div className="mt-4 space-y-4">
                  <div className="rounded-md border border-lime/20 bg-lime/10 p-3 text-sm leading-6 text-lime">
                    已选择口播文案，下一步请选择声音并生成视频。
                  </div>
                  <div className="min-w-0 rounded-md border border-white/10 bg-white/[0.035] p-4">
                    <p className="text-sm font-semibold text-white">{selectedScript.title}</p>
                    <p className="mt-2 line-clamp-4 whitespace-pre-wrap break-words text-sm leading-7 text-slate-300 [overflow-wrap:anywhere]">{selectedScript.script}</p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      href={`/studio/avatar?script_text=${encodeURIComponent(selectedScript.script)}`}
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-cyan/30 px-4 text-sm font-semibold text-cyan hover:bg-cyan/10"
                    >
                      <Mic2 size={16} />
                      选择声音
                    </Link>
                    <Link
                      href={`/studio/avatar?script_text=${encodeURIComponent(selectedScript.script)}`}
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90"
                    >
                      <Video size={16} />
                      进入视频生成
                    </Link>
                  </div>
                </div>
              )}
            </section>
          </section>

          <aside className="min-w-0 max-w-full space-y-4 xl:w-[260px]">
            <section className="rounded-lg border border-white/10 bg-panel/80 p-4 shadow-glow">
              <h2 className="text-base font-semibold text-white">流程进度</h2>
              <div className="mt-4 space-y-3">
                {progressSteps.map((step) => (
                  <div
                    key={step.key}
                    className={[
                      "flex min-w-0 items-center gap-3 rounded-md border px-3 py-3 text-sm",
                      step.status === "completed"
                        ? "border-lime/25 bg-lime/10 text-lime"
                        : step.status === "active"
                          ? "border-cyan/35 bg-cyan/10 text-cyan"
                          : "border-white/10 bg-white/[0.03] text-slate-500",
                    ].join(" ")}
                  >
                    {step.status === "completed" ? <CheckCircle2 size={17} /> : <Circle size={17} />}
                    <span className="min-w-0 flex-1 truncate">{step.label}</span>
                    <span className="shrink-0 text-xs">{step.status === "completed" ? "完成" : step.status === "active" ? "当前" : "未开始"}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-panel/80 p-4 shadow-glow">
              <h2 className="text-base font-semibold text-white">下一步</h2>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-400">
                <p className="flex gap-2">
                  <PlayCircle className="mt-1 shrink-0 text-cyan" size={16} />
                  {selectedScript ? "已选择口播文案，可以进入声音选择。" : "先确认一条口播文案，再进入数字人口播生成。"}
                </p>
                <p className="flex gap-2">
                  <Mic2 className="mt-1 shrink-0 text-cyan" size={16} />
                  可在生成页选择声音或使用默认声音。
                </p>
                <Link
                  href="/studio/avatar"
                  className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-cyan/30 px-3 text-sm font-semibold text-cyan hover:bg-cyan/10"
                >
                  <Video size={16} />
                  进入视频生成
                </Link>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
