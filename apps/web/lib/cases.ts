import type { Locale } from "@/components/LanguageProvider";

export type CaseLocale = Locale;

export type CustomerCase = {
  id: string;
  category: "product" | "avatar" | "commerce" | "business";
  title: Record<CaseLocale, string>;
  description: Record<CaseLocale, string>;
  thumbnailUrl: string;
  videoUrl: string;
  taskId: string;
  duration: string;
  language: CaseLocale | "multi";
  featured?: boolean;
};

export const customerCases: CustomerCase[] = [
  {
    id: "ai-avatar-production-demo",
    category: "avatar",
    title: {
      zh: "真实 AI 数字人口播演示",
      en: "Real AI Talking Avatar Demo",
      ja: "リアル AI デジタルヒューマンデモ",
      ko: "실제 AI 디지털 휴먼 데모",
      es: "Demo real de avatar IA",
      fr: "Demo reelle d'avatar IA",
      ru: "Реальное демо AI-аватара",
    },
    description: {
      zh: "生产环境完整链路生成：输入文案、自动配音、MuseTalk 数字人口播和 MP4 下载。",
      en: "Generated through the production flow: script input, synthesized voice, MuseTalk avatar video, and MP4 delivery.",
      ja: "本番フローで生成：台本入力、音声合成、MuseTalk デジタルヒューマン動画、MP4 出力まで。",
      ko: "프로덕션 플로우로 생성: 대본 입력, 음성 합성, MuseTalk 디지털 휴먼 영상, MP4 제공까지.",
      es: "Generado con el flujo de produccion: guion, voz sintetizada, avatar MuseTalk y entrega MP4.",
      fr: "Genere avec le flux de production : script, voix synthetisee, avatar MuseTalk et livraison MP4.",
      ru: "Создано в production-процессе: сценарий, синтез речи, MuseTalk-аватар и MP4.",
    },
    thumbnailUrl: "/avatars/ai_female_01.png",
    videoUrl: "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatar-results/133d03f9-05db-455d-9559-2c5ad9e14982/ce39f0da8f8c4794ab015758ed7da048.mp4?",
    taskId: "133d03f9-05db-455d-9559-2c5ad9e14982",
    duration: "13.032s",
    language: "zh",
    featured: true,
  },
  {
    id: "product-launch-demo",
    category: "product",
    title: {
      zh: "产品卖点讲解",
      en: "Product Launch Demo",
      ja: "商品ローンチデモ",
      ko: "제품 론칭 데모",
      es: "Demo de lanzamiento de producto",
      fr: "Demo de lancement produit",
      ru: "Демо запуска продукта",
    },
    description: {
      zh: "上传真人口播素材和产品配音，生成适合首页、广告和社媒投放的数字人口播短片。",
      en: "Upload presenter footage and a voiceover to create a talking avatar clip for landing pages, ads, and social channels.",
      ja: "人物映像と商品ナレーションをアップロードし、LP、広告、SNS 向けのデジタルヒューマン動画を生成。",
      ko: "출연자 영상과 제품 보이스오버를 업로드해 랜딩페이지, 광고, SNS용 디지털 휴먼 클립을 만듭니다.",
      es: "Sube metraje del presentador y una voz para crear un clip de avatar para landings, anuncios y redes.",
      fr: "Importez une video de presentateur et une voix off pour creer un clip avatar pour pages, pubs et reseaux.",
      ru: "Загрузите видео ведущего и озвучку, чтобы создать avatar-клип для лендингов, рекламы и соцсетей.",
    },
    thumbnailUrl: "/avatars/business_female_01.png",
    videoUrl: "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatar-results/19e8db33-799a-4986-98e2-61ca00fd4329/b353170a4dcc4f0797242a84cf7d1974.mp4?",
    taskId: "19e8db33-799a-4986-98e2-61ca00fd4329",
    duration: "17.520s",
    language: "multi",
    featured: true,
  },
  {
    id: "ecommerce-short-video",
    category: "commerce",
    title: {
      zh: "电商带货短视频",
      en: "E-commerce Short Video",
      ja: "EC 販促ショート動画",
      ko: "이커머스 숏폼 영상",
      es: "Video corto e-commerce",
      fr: "Video courte e-commerce",
      ru: "Короткое e-commerce видео",
    },
    description: {
      zh: "为商品详情页、直播预热视频和投流素材快速生成真人感口播内容。",
      en: "Create human-feeling product narration for PDPs, livestream previews, and performance creatives.",
      ja: "商品ページ、ライブ告知、広告素材向けに、人が話しているような商品説明を素早く生成。",
      ko: "상품 상세 페이지, 라이브 예고, 광고 소재용으로 사람 같은 제품 내레이션을 빠르게 만듭니다.",
      es: "Crea narraciones de producto naturales para PDP, previas de directo y creatividades de rendimiento.",
      fr: "Creez des narrations produit naturelles pour fiches produit, lives et creatives publicitaires.",
      ru: "Создавайте живую товарную подачу для карточек, live-анонсов и рекламных креативов.",
    },
    thumbnailUrl: "/avatars/business_male_01.png",
    videoUrl: "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatar-results/56b1468c-f7a4-4cba-bab4-aaaa706a6ee8/e4385c1df5af4906a441828a1fe11126.mp4?",
    taskId: "56b1468c-f7a4-4cba-bab4-aaaa706a6ee8",
    duration: "15.552s",
    language: "multi",
  },
  {
    id: "business-training",
    category: "business",
    title: {
      zh: "企业培训说明",
      en: "Business Training",
      ja: "企業研修動画",
      ko: "비즈니스 교육 영상",
      es: "Formacion empresarial",
      fr: "Formation entreprise",
      ru: "Корпоративное обучение",
    },
    description: {
      zh: "将业务汇报、流程说明和培训脚本转成统一风格的视频资产。",
      en: "Turn reports, process explainers, and training scripts into consistent video assets.",
      ja: "業務報告、手順説明、研修台本を統一感のある動画資産へ変換。",
      ko: "업무 보고, 프로세스 설명, 교육 대본을 일관된 영상 자산으로 전환합니다.",
      es: "Convierte informes, explicaciones de proceso y guiones de formacion en activos de video consistentes.",
      fr: "Transformez rapports, explications de processus et scripts de formation en videos coherentes.",
      ru: "Преобразуйте отчеты, инструкции и учебные сценарии в единые видео-материалы.",
    },
    thumbnailUrl: "/logo-transparent.png",
    videoUrl: "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatar-results/e81a5831-6ff2-49b4-9e73-23742138b7ef/76cc7d699bac46cfb32f5da615919240.mp4?",
    taskId: "e81a5831-6ff2-49b4-9e73-23742138b7ef",
    duration: "15.216s",
    language: "multi",
  },
];

export function getFeaturedCases() {
  return customerCases.filter((item) => item.featured).slice(0, 2);
}
