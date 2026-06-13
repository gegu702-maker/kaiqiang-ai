"use client";

import Image from "next/image";
import { useActionState } from "react";
import { BriefcaseBusiness, CheckCircle2, ChevronDown, Clapperboard, Mail, Megaphone, PlayCircle, ShoppingBag, Sparkles, UsersRound } from "lucide-react";

import { joinWaitlistAction } from "@/app/actions/waitlist";
import { useLanguage, type Locale } from "@/components/LanguageProvider";
import { customerCases, getFeaturedCases, type CaseLocale, type CustomerCase } from "@/lib/cases";

const initialWaitlistState = { ok: false, message: "" };

const copy = {
  zh: {
    demoEyebrow: "演示案例",
    demoTitle: "输入文案，\n生成真实 AI 数字人口播视频。",
    before: "真实演示",
    after: "产品介绍",
    placeholder: "真实案例生成中",
    previewSoon: "真实视频",
    examplesEyebrow: "案例展示",
    examplesTitle: "生产环境生成的真实案例视频",
    trustedTitle: "面向未来内容团队",
    trustedBody: "为内容团队、营销团队和企业提供真实数字人口播能力。",
    waitlistEyebrow: "抢先体验",
    waitlistTitle: "加入等待名单",
    waitlistBody: "告诉我们你的使用场景，优先获取新模板、案例和商业化功能。",
    email: "邮箱",
    industry: "行业",
    useCase: "使用场景",
    industryPlaceholder: "行业，例如电商 / 教育 / SaaS",
    useCasePlaceholder: "使用场景，例如产品介绍、课程视频、企业培训",
    submit: "加入等待名单",
    faqEyebrow: "FAQ",
    faqTitle: "常见问题",
    faq: [
      ["如何生成数字人视频？", "上传人物视频和音频后，系统会创建异步任务并生成口型同步的数字人口播视频。"],
      ["支持哪些格式？", "人物视频支持 mp4 / mov / webm，音频支持 wav / mp3 / m4a 等常见格式。"],
      ["免费额度是多少？", "当前 Free 套餐默认每月 3 次生成额度，适合先验证效果。"],
      ["视频生成需要多久？", "通常几分钟内完成，具体取决于素材时长、排队情况和 GPU 状态。"],
      ["是否支持商业用途？", "支持用于商业内容验证。请确保上传素材、肖像和音频拥有合法授权。"],
    ],
  },
  en: {
    demoEyebrow: "Hero Demo",
    demoTitle: "Enter a script,\ngenerate a real AI talking avatar video.",
    before: "Real Demo",
    after: "Product Demo",
    placeholder: "Real case generating",
    previewSoon: "Real video",
    examplesEyebrow: "Examples",
    examplesTitle: "Real production-generated customer examples",
    trustedTitle: "Trusted By Future Content Teams",
    trustedBody: "Built for content teams, marketers, and businesses.",
    waitlistEyebrow: "Get Early Access",
    waitlistTitle: "Join the waitlist",
    waitlistBody: "Share your use case to get early access to new templates, demos, and commercial features.",
    email: "Email",
    industry: "Industry",
    useCase: "Use Case",
    industryPlaceholder: "Industry, e.g. e-commerce / education / SaaS",
    useCasePlaceholder: "Use case, e.g. product demos, course videos, training",
    submit: "Join waitlist",
    faqEyebrow: "FAQ",
    faqTitle: "Frequently Asked Questions",
    faq: [
      ["How do I generate an AI avatar video?", "Upload a person video and an audio file. Kaiqiang AI creates an async task and generates a lip-synced talking avatar video."],
      ["Which formats are supported?", "Person videos support mp4 / mov / webm, and audio supports common formats such as wav / mp3 / m4a."],
      ["How many free credits are included?", "The current Free plan includes 3 generations per month, designed for validating results first."],
      ["How long does generation take?", "Most videos complete within minutes, depending on media length, queue status, and GPU availability."],
      ["Can I use the videos commercially?", "Commercial validation is supported. Make sure you have proper rights for uploaded footage, likeness, and audio."],
    ],
  },
  ja: {
    demoEyebrow: "デモ",
    demoTitle: "台本を入力して、\nAI アバター動画を生成。",
    before: "リアルデモ",
    after: "商品紹介",
    placeholder: "事例生成中",
    previewSoon: "動画",
    examplesEyebrow: "事例",
    examplesTitle: "本番環境で生成された事例動画",
    trustedTitle: "これからのコンテンツチームへ",
    trustedBody: "制作チーム、マーケター、企業向けにデジタルヒューマン生成を提供します。",
    waitlistEyebrow: "先行体験",
    waitlistTitle: "ウェイトリストに参加",
    waitlistBody: "利用シーンを共有すると、新テンプレートや商用機能を優先的に案内します。",
    email: "メール",
    industry: "業界",
    useCase: "利用シーン",
    industryPlaceholder: "例: EC / 教育 / SaaS",
    useCasePlaceholder: "例: 商品紹介、講座動画、企業研修",
    submit: "参加する",
    faqEyebrow: "FAQ",
    faqTitle: "よくある質問",
    faq: [["どう生成しますか？", "人物動画と音声をアップロードすると、リップシンク動画を生成します。"], ["対応形式は？", "動画は mp4 / mov / webm、音声は wav / mp3 / m4a などに対応します。"], ["無料枠は？", "Free は月3回の生成枠です。"], ["生成時間は？", "通常は数分です。素材時間や GPU 状況で変わります。"], ["商用利用できますか？", "可能です。素材、肖像、音声の権利を確認してください。"]],
  },
  ko: {
    demoEyebrow: "데모",
    demoTitle: "대본을 입력하면\nAI 디지털 휴먼 영상 생성.",
    before: "실제 데모",
    after: "제품 소개",
    placeholder: "사례 생성 중",
    previewSoon: "영상",
    examplesEyebrow: "사례",
    examplesTitle: "프로덕션에서 생성한 실제 사례 영상",
    trustedTitle: "미래 콘텐츠 팀을 위한 플랫폼",
    trustedBody: "콘텐츠 팀, 마케팅 팀, 기업에 디지털 휴먼 기능을 제공합니다.",
    waitlistEyebrow: "얼리 액세스",
    waitlistTitle: "대기 명단 참여",
    waitlistBody: "사용 시나리오를 알려주시면 새 템플릿과 기능을 우선 안내합니다.",
    email: "이메일",
    industry: "업종",
    useCase: "사용 사례",
    industryPlaceholder: "예: 이커머스 / 교육 / SaaS",
    useCasePlaceholder: "예: 제품 소개, 강의 영상, 기업 교육",
    submit: "대기 명단 참여",
    faqEyebrow: "FAQ",
    faqTitle: "자주 묻는 질문",
    faq: [["어떻게 생성하나요?", "인물 영상과 음성을 업로드하면 립싱크 디지털 휴먼 영상을 생성합니다."], ["지원 형식은?", "영상은 mp4 / mov / webm, 음성은 wav / mp3 / m4a 등을 지원합니다."], ["무료 한도는?", "Free 플랜은 월 3회 생성입니다."], ["얼마나 걸리나요?", "보통 몇 분 내 완료되며 소재 길이와 GPU 상태에 따라 달라집니다."], ["상업적으로 쓸 수 있나요?", "가능합니다. 업로드 소재와 초상권, 음성 권리를 확인하세요."]],
  },
  es: {
    demoEyebrow: "Demo",
    demoTitle: "Introduce un guion,\ngenera un avatar IA real.",
    before: "Demo real",
    after: "Demo de producto",
    placeholder: "Caso generandose",
    previewSoon: "Video",
    examplesEyebrow: "Ejemplos",
    examplesTitle: "Casos reales generados en produccion",
    trustedTitle: "Para equipos de contenido",
    trustedBody: "Capacidades de avatar IA para equipos de contenido, marketing y empresas.",
    waitlistEyebrow: "Acceso anticipado",
    waitlistTitle: "Unete a la lista",
    waitlistBody: "Comparte tu caso de uso para recibir nuevas plantillas y funciones antes.",
    email: "Email",
    industry: "Industria",
    useCase: "Caso de uso",
    industryPlaceholder: "Industria, p. ej. ecommerce / educacion / SaaS",
    useCasePlaceholder: "P. ej. demos de producto, cursos, formacion",
    submit: "Unirme",
    faqEyebrow: "FAQ",
    faqTitle: "Preguntas frecuentes",
    faq: [["Como genero un video?", "Sube video humano y audio. El sistema genera un avatar con lip-sync."], ["Formatos soportados?", "Video mp4 / mov / webm; audio wav / mp3 / m4a."], ["Creditos gratis?", "Free incluye 3 generaciones al mes."], ["Cuanto tarda?", "Normalmente unos minutos, segun duracion y cola GPU."], ["Uso comercial?", "Si, si tienes derechos sobre imagen, audio y materiales."]],
  },
  fr: {
    demoEyebrow: "Demo",
    demoTitle: "Saisissez un script,\ngenerez un avatar IA reel.",
    before: "Demo reelle",
    after: "Demo produit",
    placeholder: "Cas en generation",
    previewSoon: "Video",
    examplesEyebrow: "Exemples",
    examplesTitle: "Cas reels generes en production",
    trustedTitle: "Pour les equipes contenu",
    trustedBody: "Des capacites digital human pour contenu, marketing et entreprises.",
    waitlistEyebrow: "Acces anticipe",
    waitlistTitle: "Rejoindre la liste",
    waitlistBody: "Partagez votre cas d'usage pour recevoir les nouveaux modeles et fonctions en priorite.",
    email: "Email",
    industry: "Secteur",
    useCase: "Cas d'usage",
    industryPlaceholder: "Secteur, ex. e-commerce / education / SaaS",
    useCasePlaceholder: "Ex. demo produit, cours, formation",
    submit: "Rejoindre",
    faqEyebrow: "FAQ",
    faqTitle: "Questions frequentes",
    faq: [["Comment generer une video ?", "Importez une video humaine et un audio. Le systeme genere un avatar avec lip-sync."], ["Quels formats ?", "Video mp4 / mov / webm, audio wav / mp3 / m4a."], ["Credits gratuits ?", "Free inclut 3 generations par mois."], ["Combien de temps ?", "Quelques minutes en general, selon la duree et la file GPU."], ["Usage commercial ?", "Oui, si vous avez les droits sur image, audio et medias."]],
  },
  ru: {
    demoEyebrow: "Демо",
    demoTitle: "Введите сценарий,\nсоздайте AI-аватар видео.",
    before: "Реальное демо",
    after: "Демо продукта",
    placeholder: "Кейс генерируется",
    previewSoon: "Видео",
    examplesEyebrow: "Примеры",
    examplesTitle: "Реальные видео из production-процесса",
    trustedTitle: "Для команд контента",
    trustedBody: "Digital human возможности для контента, маркетинга и бизнеса.",
    waitlistEyebrow: "Ранний доступ",
    waitlistTitle: "Присоединиться к списку",
    waitlistBody: "Опишите ваш сценарий, чтобы первыми получить новые шаблоны и функции.",
    email: "Email",
    industry: "Индустрия",
    useCase: "Сценарий",
    industryPlaceholder: "Напр. e-commerce / education / SaaS",
    useCasePlaceholder: "Напр. демо продукта, курсы, обучение",
    submit: "Присоединиться",
    faqEyebrow: "FAQ",
    faqTitle: "Частые вопросы",
    faq: [["Как создать видео?", "Загрузите видео человека и аудио, система создаст lip-sync аватар."], ["Какие форматы?", "Видео mp4 / mov / webm, аудио wav / mp3 / m4a."], ["Бесплатный лимит?", "Free включает 3 генерации в месяц."], ["Сколько времени?", "Обычно несколько минут, зависит от длины и очереди GPU."], ["Коммерческое использование?", "Да, если у вас есть права на материалы, образ и аудио."]],
  },
};

const exampleIcons = [Megaphone, Clapperboard, ShoppingBag, BriefcaseBusiness];

export function HomeConversionSections() {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <>
      <HeroDemoShowcase current={current} />
      <CustomerExamples current={current} />
      <TrustedByFutureTeams current={current} />
      <WaitlistForm current={current} locale={locale} />
      <HomeFAQ current={current} />
    </>
  );
}

function HeroDemoShowcase({ current }: { current: (typeof copy)["zh"] }) {
  const { locale } = useLanguage();
  const caseLocale: CaseLocale = locale === "zh" ? "zh" : "en";
  const featuredCases = getFeaturedCases();
  const beforeCase = featuredCases[0] ?? customerCases[0];
  const afterCase = featuredCases[1] ?? customerCases[1] ?? beforeCase;

  return (
    <section className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-20">
      <div className="grid gap-9 lg:grid-cols-[0.38fr_0.62fr] lg:items-center">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.demoEyebrow}</p>
          <h2 className="mt-4 whitespace-pre-line text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.demoTitle}</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <DemoVideo label={current.before} item={beforeCase} locale={caseLocale} placeholder={current.placeholder} />
          <DemoVideo label={current.after} item={afterCase} locale={caseLocale} placeholder={current.placeholder} />
        </div>
      </div>
    </section>
  );
}

function DemoVideo({ label, item, locale, placeholder }: { label: string; item: CustomerCase; locale: CaseLocale; placeholder: string }) {
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_14px_38px_rgba(15,23,42,0.06)]">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">{label}</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{item.title[locale]}</p>
        </div>
        <Sparkles size={16} className="text-indigo-500" />
      </div>
      <div className="relative aspect-video overflow-hidden bg-slate-950">
        <video className="h-full w-full object-cover" src={item.videoUrl || undefined} poster={item.thumbnailUrl} controls muted autoPlay loop playsInline />
        {!item.videoUrl ? <p className="absolute bottom-3 left-3 right-3 rounded-md bg-slate-950/72 px-3 py-2 text-xs leading-5 text-white backdrop-blur">{placeholder}</p> : null}
      </div>
    </article>
  );
}

function CustomerExamples({ current }: { current: (typeof copy)["zh"] }) {
  const { locale } = useLanguage();
  const caseLocale: CaseLocale = locale === "zh" ? "zh" : "en";

  return (
    <section id="examples" className="border-y border-slate-200/70 bg-white/68 px-6 py-16 sm:px-10 lg:py-20">
      <div className="mx-auto max-w-[1280px]">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.examplesEyebrow}</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.examplesTitle}</h2>
        </div>
        <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {customerCases.map((item, index) => {
            const Icon = exampleIcons[index];
            const title = item.title[caseLocale];
            const desc = item.description[caseLocale];
            return (
              <article key={title} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_14px_38px_rgba(15,23,42,0.05)]">
                <div className="relative aspect-video bg-slate-100">
                  <Image src={item.thumbnailUrl} alt={title} fill sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw" className="object-cover" />
                  <div className="absolute left-3 top-3 grid size-9 place-items-center rounded-lg bg-white/90 text-slate-950 shadow-sm backdrop-blur">
                    {Icon ? <Icon size={18} /> : <PlayCircle size={18} />}
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="text-base font-semibold text-slate-950">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{desc}</p>
                  <div className="mt-4 overflow-hidden rounded-md border border-slate-200 bg-slate-950">
                    <div className="relative aspect-video">
                      {item.videoUrl ? (
                        <video className="h-full w-full object-cover" src={item.videoUrl} poster={item.thumbnailUrl} controls muted playsInline />
                      ) : (
                        <Image src={item.thumbnailUrl} alt={`${title} preview`} fill sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw" className="object-cover opacity-70" />
                      )}
                      <div className="absolute inset-0 grid place-items-center bg-slate-950/30 text-white">
                        <div className="flex items-center gap-2 rounded-full bg-slate-950/70 px-3 py-2 text-xs font-semibold backdrop-blur">
                          <PlayCircle size={15} />
                          {item.videoUrl ? item.category : current.previewSoon}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function TrustedByFutureTeams({ current }: { current: (typeof copy)["zh"] }) {
  return (
    <section className="mx-auto max-w-[1280px] px-6 py-14 sm:px-10">
      <div className="grid gap-5 rounded-lg border border-slate-200 bg-slate-950 p-6 text-white shadow-[0_16px_44px_rgba(15,23,42,0.13)] sm:p-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-lg bg-white/10">
            <UsersRound size={22} />
          </div>
          <h2 className="text-2xl font-semibold">{current.trustedTitle}</h2>
        </div>
        <p className="text-base leading-7 text-slate-300">{current.trustedBody}</p>
      </div>
    </section>
  );
}

function WaitlistForm({ current, locale }: { current: (typeof copy)["zh"]; locale: Locale }) {
  const [state, action] = useActionState(joinWaitlistAction, initialWaitlistState);

  return (
    <section id="contact" className="mx-auto max-w-[1280px] px-6 py-16 sm:px-10 lg:py-20">
      <div className="grid gap-8 rounded-lg border border-slate-200 bg-white p-6 shadow-[0_14px_38px_rgba(15,23,42,0.05)] sm:p-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-start">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.waitlistEyebrow}</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.waitlistTitle}</h2>
          <p className="mt-4 text-base leading-7 text-slate-500">{current.waitlistBody}</p>
        </div>
        <form action={action} className="grid gap-4">
          <input type="hidden" name="locale" value={locale} />
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.email}
            <input name="email" type="email" required className="h-12 rounded-md border border-slate-200 bg-white px-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder="you@example.com" />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.industry}
            <input name="industry" required className="h-12 rounded-md border border-slate-200 bg-white px-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder={current.industryPlaceholder} />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-slate-800">
            {current.useCase}
            <textarea name="use_case" required className="min-h-28 rounded-md border border-slate-200 bg-white px-3 py-3 text-slate-950 outline-none ring-indigo-200 focus:ring-2" placeholder={current.useCasePlaceholder} />
          </label>
          {state.message ? (
            <p className={`flex items-center gap-2 text-sm ${state.ok ? "text-emerald-700" : "text-rose-600"}`}>
              {state.ok ? <CheckCircle2 size={16} /> : <Mail size={16} />}
              {state.message}
            </p>
          ) : null}
          <button type="submit" className="inline-flex h-12 items-center justify-center rounded-md bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800">
            {current.submit}
          </button>
        </form>
      </div>
    </section>
  );
}

function HomeFAQ({ current }: { current: (typeof copy)["zh"] }) {
  return (
    <section className="border-t border-slate-200/70 bg-white/68 px-6 py-16 sm:px-10 lg:py-20">
      <div className="mx-auto max-w-[980px]">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{current.faqEyebrow}</p>
        <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{current.faqTitle}</h2>
        <div className="mt-8 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {current.faq.map(([question, answer]) => (
            <details key={question} className="group p-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-semibold text-slate-950">
                {question}
                <ChevronDown size={18} className="shrink-0 text-slate-400 transition group-open:rotate-180" />
              </summary>
              <p className="mt-3 text-sm leading-6 text-slate-500">{answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
