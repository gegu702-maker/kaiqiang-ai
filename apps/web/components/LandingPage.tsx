"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Captions, Database, Gauge, Mic2, MousePointerClick, PlayCircle, ShieldCheck, Sparkles, UserRoundCheck, Video, Zap } from "lucide-react";

import { HomeConversionSections } from "@/components/HomeConversionSections";
import { useLanguage } from "@/components/LanguageProvider";
import { trackEvent } from "@/lib/analytics";

const copy = {
  zh: {
    titlePrefix: "上传视频和音频",
    titleAccent: "自动生成",
    titleSuffix: "数字人口播",
    subtitle: "Kaiqiang.ai 将真人视频与口播音频合成为自然口型同步的 AI 数字人视频，适合产品介绍、课程讲解和电商内容。",
    start: "立即开始",
    examples: "查看示例",
    badge: "AI 数字人口播视频创作平台",
    flow: ["上传视频", "上传音频", "自动生成数字人口播"],
    whyTitle: "为什么选择 Kaiqiang AI",
    whySubtitle: "围绕真实数字人口播生成流程打造，减少学习成本，让创作者更快得到可用成片。",
    cards: [
      ["AI 数字人口播", "真实数字人口播视频", "一键生成"],
      ["AI 配音", "多种语音风格", "自然流畅"],
      ["自动字幕", "智能识别生成字幕", "支持多语言"],
      ["高效创作", "简单高效的创作流程", "节省时间成本"],
    ],
    trust: [
      ["快速生成", "异步生成任务，清晰展示排队、生成和上传进度。"],
      ["真实数字人", "基于真实人物视频生成自然口型同步的 AI 数字人口播。"],
      ["安全存储", "生成素材和结果文件通过云端存储管理，访问更稳定。"],
      ["简单易用", "上传视频和音频即可开始，适合快速验证内容创意。"],
    ],
  },
  en: {
    titlePrefix: "Upload video and audio",
    titleAccent: "Generate",
    titleSuffix: "AI talking avatars",
    subtitle: "Kaiqiang.ai turns person footage and voice audio into natural lip-synced digital human videos for product demos, courses, and commerce.",
    start: "Get Started",
    examples: "View Examples",
    badge: "AI Digital Human Video Creation Platform",
    flow: ["Upload video", "Upload audio", "Generate talking avatar"],
    whyTitle: "Why Kaiqiang AI",
    whySubtitle: "Built around a real avatar generation workflow so creators can move from upload to usable video with less friction.",
    cards: [
      ["Digital Human Videos", "Real digital human talking videos", "One-click generation"],
      ["AI Voiceover", "Multiple voice styles", "Natural and fluent"],
      ["Auto Captions", "Smart subtitle generation", "Multilingual support"],
      ["Efficient Creation", "A simpler creative workflow", "Save time and cost"],
    ],
    trust: [
      ["Fast Generation", "Async generation tasks with clear queue, render, and upload progress."],
      ["Real AI Avatar", "Create natural AI talking avatar videos from real person footage."],
      ["Secure Storage", "Uploaded assets and generated videos are managed with cloud storage."],
      ["Easy to Use", "Upload a video and audio file to quickly validate creative ideas."],
    ],
  },
  ja: {
    titlePrefix: "動画と音声をアップロード",
    titleAccent: "自動生成",
    titleSuffix: "AI アバター動画",
    subtitle: "Kaiqiang.ai は人物動画と音声を自然なリップシンクのデジタルヒューマン動画に変換します。",
    start: "今すぐ開始",
    examples: "事例を見る",
    badge: "AI デジタルヒューマン動画作成プラットフォーム",
    flow: ["動画アップロード", "音声アップロード", "アバター動画を生成"],
    whyTitle: "Kaiqiang AI を選ぶ理由",
    whySubtitle: "実際の生成フローに合わせて設計され、少ない手間で使える動画を作れます。",
    cards: [["AI アバター動画", "自然なトーク動画", "ワンクリック生成"], ["AI 音声", "複数の音声スタイル", "自然で滑らか"], ["自動字幕", "スマート字幕生成", "多言語対応"], ["効率的な制作", "シンプルな制作フロー", "時間を節約"]],
    trust: [["高速生成", "キュー、生成、アップロード進行を明確に表示。"], ["リアルなアバター", "人物動画から自然なリップシンク動画を生成。"], ["安全な保存", "素材と生成結果をクラウドで管理。"], ["使いやすい", "動画と音声をアップロードするだけで開始できます。"]],
  },
  ko: {
    titlePrefix: "영상과 음성을 업로드",
    titleAccent: "자동 생성",
    titleSuffix: "AI 디지털 휴먼",
    subtitle: "Kaiqiang.ai는 인물 영상과 음성을 자연스러운 립싱크 디지털 휴먼 영상으로 변환합니다.",
    start: "바로 시작",
    examples: "예시 보기",
    badge: "AI 디지털 휴먼 영상 제작 플랫폼",
    flow: ["영상 업로드", "음성 업로드", "디지털 휴먼 생성"],
    whyTitle: "Kaiqiang AI를 선택하는 이유",
    whySubtitle: "실제 생성 흐름에 맞춰 설계되어 더 빠르게 사용 가능한 영상을 만들 수 있습니다.",
    cards: [["AI 디지털 휴먼", "실감 나는 말하기 영상", "원클릭 생성"], ["AI 보이스", "다양한 음성 스타일", "자연스러운 음성"], ["자동 자막", "스마트 자막 생성", "다국어 지원"], ["효율적 제작", "간단한 제작 흐름", "시간 절약"]],
    trust: [["빠른 생성", "대기열, 생성, 업로드 진행을 명확히 표시합니다."], ["실감형 아바타", "인물 영상 기반의 자연스러운 립싱크 영상을 만듭니다."], ["안전한 저장", "소재와 결과물을 클라우드로 관리합니다."], ["쉬운 사용", "영상과 음성만 업로드하면 시작할 수 있습니다."]],
  },
  es: {
    titlePrefix: "Sube video y audio",
    titleAccent: "Genera",
    titleSuffix: "avatares IA",
    subtitle: "Kaiqiang.ai convierte video humano y audio en videos de avatar con sincronizacion labial natural.",
    start: "Empezar",
    examples: "Ver ejemplos",
    badge: "Plataforma de videos con humanos digitales IA",
    flow: ["Subir video", "Subir audio", "Generar avatar"],
    whyTitle: "Por que Kaiqiang AI",
    whySubtitle: "Diseñado alrededor del flujo real de generacion para obtener videos utilizables con menos friccion.",
    cards: [["Videos con avatar IA", "Videos realistas", "Generacion en un clic"], ["Voz IA", "Varios estilos", "Natural y fluida"], ["Subtitulos automaticos", "Generacion inteligente", "Soporte multilingue"], ["Creacion eficiente", "Flujo simple", "Ahorra tiempo"]],
    trust: [["Generacion rapida", "Tareas asincronas con progreso claro."], ["Avatar realista", "Videos con lip-sync desde metraje humano."], ["Almacenamiento seguro", "Archivos gestionados en la nube."], ["Facil de usar", "Sube video y audio para empezar."]],
  },
  fr: {
    titlePrefix: "Importez video et audio",
    titleAccent: "Generez",
    titleSuffix: "des avatars IA",
    subtitle: "Kaiqiang.ai transforme une video humaine et une voix en video de digital human avec lip-sync naturel.",
    start: "Commencer",
    examples: "Voir exemples",
    badge: "Plateforme de creation video digital human IA",
    flow: ["Importer video", "Importer audio", "Generer l'avatar"],
    whyTitle: "Pourquoi Kaiqiang AI",
    whySubtitle: "Concu autour d'un vrai flux de generation pour obtenir plus vite une video utilisable.",
    cards: [["Videos avatar IA", "Videos realistes", "Generation en un clic"], ["Voix IA", "Plusieurs styles", "Naturelle et fluide"], ["Sous-titres auto", "Generation intelligente", "Multilingue"], ["Creation efficace", "Flux simple", "Gain de temps"]],
    trust: [["Generation rapide", "Progression claire de la file, du rendu et de l'upload."], ["Avatar realiste", "Lip-sync naturel depuis une video humaine."], ["Stockage securise", "Medias et resultats geres dans le cloud."], ["Simple", "Importez video et audio pour commencer."]],
  },
  ru: {
    titlePrefix: "Загрузите видео и аудио",
    titleAccent: "Создайте",
    titleSuffix: "AI-аватар видео",
    subtitle: "Kaiqiang.ai превращает видео человека и голос в естественное видео с синхронизацией губ.",
    start: "Начать",
    examples: "Смотреть примеры",
    badge: "Платформа AI digital human видео",
    flow: ["Загрузить видео", "Загрузить аудио", "Создать аватар"],
    whyTitle: "Почему Kaiqiang AI",
    whySubtitle: "Построено вокруг реального процесса генерации, чтобы быстрее получить готовое видео.",
    cards: [["AI-аватар видео", "Реалистичные видео", "Генерация в один клик"], ["AI-голос", "Разные стили", "Естественно"], ["Автосубтитры", "Умная генерация", "Много языков"], ["Эффективность", "Простой процесс", "Экономия времени"]],
    trust: [["Быстрая генерация", "Понятный прогресс очереди, рендера и загрузки."], ["Реальный аватар", "Естественный lip-sync из видео человека."], ["Безопасное хранение", "Материалы и результаты в облаке."], ["Просто", "Загрузите видео и аудио, чтобы начать."]],
  },
};

const icons = [Video, Mic2, Captions, Zap];
const trustIcons = [Gauge, UserRoundCheck, ShieldCheck, MousePointerClick];

export function LandingPage({ startHref }: { startHref: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <main
      className="min-h-screen overflow-hidden text-slate-950"
      style={{
        background:
          "radial-gradient(circle at 73% 38%, rgba(99,102,241,0.12), transparent 34%), radial-gradient(circle at 18% 12%, rgba(219,234,254,0.42), transparent 24%), linear-gradient(180deg, #ffffff 0%, #fbfcff 58%, #ffffff 100%)",
      }}
    >
      <section className="relative mx-auto grid min-h-[680px] max-w-[1440px] items-center gap-10 px-6 pb-10 pt-14 sm:px-10 lg:grid-cols-[0.42fr_0.58fr] lg:px-20 lg:pb-8 lg:pt-16">
        <div className="pointer-events-none absolute right-[-7%] top-[5%] hidden size-[760px] rounded-full border border-slate-200/35 lg:block" />
        <div className="pointer-events-none absolute right-[8%] top-[20%] hidden size-[500px] rounded-full border border-indigo-100/35 lg:block" />
        <div className="pointer-events-none absolute right-[32%] top-[17%] hidden size-1.5 rounded-full bg-indigo-200/60 lg:block" />

        <div className="relative z-20 max-w-[540px] space-y-8 lg:-mt-10 lg:min-w-[540px] lg:pl-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/72 px-4 py-2 text-sm font-medium text-slate-600 shadow-[0_8px_30px_rgba(15,23,42,0.035)] backdrop-blur-xl">
            <Sparkles size={15} className="text-violet-500" />
            {current.badge}
          </div>

          <div className="space-y-6">
            <h1 className="max-w-[640px] text-4xl font-semibold leading-[1.12] text-slate-900 sm:text-6xl lg:text-[54px]">
              <span className="block">{current.titlePrefix}</span>
              <span className="block">
                <span className="bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-500 bg-clip-text font-semibold text-transparent">
                  {current.titleAccent}
                </span>{" "}
                {current.titleSuffix}
              </span>
            </h1>
            <p className="max-w-[500px] whitespace-pre-line text-lg font-normal leading-8 text-slate-500">
              {current.subtitle}
            </p>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
              {current.flow.map((item, index) => (
                <div key={item} className="flex items-center gap-2">
                  <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 shadow-sm">{item}</span>
                  {index < current.flow.length - 1 ? <span className="text-slate-300">→</span> : null}
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-5 pt-1">
            <Link
              href={startHref}
              onClick={() => trackEvent("click_start_button", { source: "home_hero", href: startHref })}
              className="inline-flex h-13 min-w-[152px] items-center justify-center gap-2 rounded-full bg-slate-950 px-6 text-base font-semibold text-white shadow-[0_16px_38px_rgba(15,23,42,0.13)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              {current.start}
              <ArrowUpRight size={18} />
            </Link>
            <a
              href="#examples"
              onClick={() => trackEvent("click_view_demo", { source: "home_hero" })}
              className="inline-flex h-13 min-w-[162px] items-center justify-center gap-3 rounded-full border border-slate-200 bg-white/72 px-6 text-base font-semibold text-slate-900 shadow-[0_10px_30px_rgba(15,23,42,0.045)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:bg-white"
            >
              <PlayCircle size={21} />
              {current.examples}
            </a>
          </div>
        </div>

        <div className="relative z-10 flex min-h-[360px] justify-center lg:min-h-[620px] lg:justify-end lg:overflow-visible">
          <div className="relative flex size-[260px] items-center justify-center sm:size-[420px] lg:size-[600px]">
            <div className="absolute inset-[-16%] rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.16)_0%,rgba(219,225,255,0.18)_36%,rgba(255,255,255,0)_70%)] blur-2xl" />
            <div className="absolute inset-[8%] rounded-full bg-white/32 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]" />
            <div className="absolute inset-[3%] rounded-full border border-white/70" />
            <div className="absolute inset-[18%] rounded-full border border-slate-200/55" />
            <Image
              src="/logo-transparent.png"
              alt="KAIQIANG.AI brand logo"
              fill
              sizes="(min-width: 1024px) 600px, (min-width: 640px) 420px, 260px"
              className="relative scale-[1.02] object-contain opacity-[0.96] drop-shadow-[0_30px_52px_rgba(15,23,42,0.18)]"
              priority
            />
          </div>
        </div>
      </section>

      <HomeConversionSections />

      <section className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-24">
        <div className="grid gap-4 sm:grid-cols-2 min-[1180px]:grid-cols-4">
          {current.cards.map(([title, desc], index) => {
            const Icon = icons[index];
            return (
              <article key={title} className="group rounded-lg border border-slate-200/65 bg-white/66 p-6 shadow-[0_12px_36px_rgba(15,23,42,0.04)] backdrop-blur-xl transition duration-300 hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white/86">
                <div className="grid size-12 place-items-center rounded-lg bg-slate-950 text-white shadow-[0_10px_24px_rgba(15,23,42,0.11)] transition group-hover:scale-[1.03]">
                  <Icon size={22} />
                </div>
                <div className="mt-6">
                  <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-500">{desc}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{current.cards[index][2]}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-y border-slate-200/70 bg-white/62 px-6 py-16 sm:px-10 lg:py-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="max-w-2xl">
            <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              <Database size={16} className="text-indigo-500" />
              {current.whyTitle}
            </p>
            <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.whyTitle}</p>
            <p className="mt-4 text-base leading-7 text-slate-500">{current.whySubtitle}</p>
          </div>
          <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {current.trust.map(([title, desc], index) => {
              const Icon = trustIcons[index];
              return (
                <article key={title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-[0_14px_36px_rgba(15,23,42,0.045)]">
                  <div className="grid size-11 place-items-center rounded-lg bg-slate-100 text-slate-900">
                    <Icon size={21} />
                  </div>
                  <h2 className="mt-5 text-lg font-semibold text-slate-950">{title}</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-500">{desc}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
