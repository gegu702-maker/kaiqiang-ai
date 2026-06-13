"use client";

import { ArrowRight, BadgeCheck, Clock } from "lucide-react";
import Link from "next/link";

import { useLanguage } from "@/components/LanguageProvider";
import { avatarStudioTemplates, sceneLabel } from "@/lib/avatarTemplates";

const copy = {
  zh: {
    title: "数字人模板库",
    subtitle: "先用官方模板降低生成门槛。模板视频陆续接入中，已上线后可直接带入 Studio。",
    free: "免费",
    paid: "套餐内",
    comingSoon: "模板视频即将上线",
    useTemplate: "选择模板",
  },
  en: {
    title: "Avatar Template Library",
    subtitle: "Start from official templates to reduce setup work. Template videos are being connected and can be used in Studio once available.",
    free: "Free",
    paid: "Included",
    comingSoon: "Template video coming soon",
    useTemplate: "Use Template",
  },
  ja: {
    title: "アバターテンプレート",
    subtitle: "公式テンプレートから始めると設定の手間を減らせます。テンプレート動画は順次接続され、利用可能になると Studio で使えます。",
    free: "無料",
    paid: "プラン内",
    comingSoon: "テンプレート動画はまもなく公開",
    useTemplate: "テンプレートを選択",
  },
  ko: {
    title: "아바타 템플릿 라이브러리",
    subtitle: "공식 템플릿으로 시작해 설정 부담을 줄이세요. 템플릿 영상은 순차 연결되며 준비되면 Studio에서 사용할 수 있습니다.",
    free: "무료",
    paid: "플랜 포함",
    comingSoon: "템플릿 영상 준비 중",
    useTemplate: "템플릿 선택",
  },
  es: {
    title: "Biblioteca de avatares",
    subtitle: "Empieza con plantillas oficiales para reducir configuracion. Los videos de plantilla se conectaran y podran usarse en Studio.",
    free: "Gratis",
    paid: "Incluido",
    comingSoon: "Video de plantilla proximamente",
    useTemplate: "Elegir plantilla",
  },
  fr: {
    title: "Bibliotheque de modeles avatar",
    subtitle: "Demarrez avec des modeles officiels pour reduire la configuration. Les videos seront connectees puis utilisables dans Studio.",
    free: "Gratuit",
    paid: "Inclus",
    comingSoon: "Video de modele bientot disponible",
    useTemplate: "Choisir le modele",
  },
  ru: {
    title: "Библиотека аватаров",
    subtitle: "Начните с официальных шаблонов, чтобы сократить настройку. Видео шаблонов подключаются постепенно и станут доступны в Studio.",
    free: "Бесплатно",
    paid: "В тарифе",
    comingSoon: "Видео шаблона скоро будет доступно",
    useTemplate: "Выбрать шаблон",
  },
} as const;

export default function AvatarTemplatesPage() {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <main className="min-h-[calc(100vh-86px)] bg-slate-50 px-4 py-10 text-slate-950 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-7">
          <p className="text-sm font-medium text-blue-700">Templates</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{current.title}</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">{current.subtitle}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {avatarStudioTemplates.map((template) => (
            <article key={template.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div
                className="aspect-video w-full bg-cover bg-center"
                style={{ backgroundImage: `url(${template.thumbnailUrl})` }}
                aria-label={template.name[locale]}
              />
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">{template.name[locale]}</h2>
                    <p className="mt-1 text-sm text-slate-500">{locale === "en" ? template.name.zh : template.name.en}</p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                    <BadgeCheck size={13} />
                    {template.isFree ? current.free : current.paid}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-600">
                  <span className="rounded-md bg-slate-100 px-2 py-1">{sceneLabel(template.scene, locale)}</span>
                  <span className="rounded-md bg-slate-100 px-2 py-1">{template.language.toUpperCase()}</span>
                </div>
                {!template.videoUrl ? (
                  <p className="mt-4 inline-flex items-center gap-2 text-sm text-amber-700">
                    <Clock size={15} />
                    {current.comingSoon}
                  </p>
                ) : null}
                <Link
                  href={`/studio/avatar?template=${template.id}`}
                  className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500"
                >
                  {current.useTemplate}
                  <ArrowRight size={16} />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
