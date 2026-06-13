export type AvatarTemplate = {
  id: string;
  name: string;
  description: string;
  avatar_image: string;
  preview_video_url?: string;
  voice_type: "BV001_streaming" | "BV002_streaming";
  gender: "female" | "male";
  style: "business" | "tech";
  vip_only: boolean;
};

const allAvatarTemplates: AvatarTemplate[] = [
  {
    id: "business_female_01",
    name: "商务女主播",
    description: "适合知识口播、课程介绍、商业内容",
    avatar_image: "/avatars/business_female_01.png",
    preview_video_url:
      "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/template-videos/business_female_01.mp4",
    voice_type: "BV001_streaming",
    gender: "female",
    style: "business",
    vip_only: false,
  },
  {
    id: "business_male_01",
    name: "商务男主播",
    description: "适合老板IP、财经、商业观点",
    avatar_image: "/avatars/business_male_01.png",
    preview_video_url:
      "https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/template-videos/business_male_01.mp4",
    voice_type: "BV002_streaming",
    gender: "male",
    style: "business",
    vip_only: false,
  },
  {
    id: "ai_female_01",
    name: "AI女主播",
    description: "适合AI资讯、科技口播、产品介绍",
    avatar_image: "/avatars/ai_female_01.png",
    voice_type: "BV001_streaming",
    gender: "female",
    style: "tech",
    vip_only: false,
  },
];

export const avatarTemplates: AvatarTemplate[] = allAvatarTemplates.filter((template) =>
  ["business_female_01", "business_male_01"].includes(template.id),
);

export function getAvatarTemplate(id: string | null | undefined) {
  return allAvatarTemplates.find((template) => template.id === id) ?? avatarTemplates[0];
}

export type AvatarStudioTemplate = {
  id: string;
  name: {
    zh: string;
    en: string;
    ja: string;
    ko: string;
    es: string;
    fr: string;
    ru: string;
  };
  thumbnailUrl: string;
  language: "zh" | "en" | "multi";
  scene: "product" | "talking" | "sales" | "tutorial";
  isFree: boolean;
  videoUrl: string | null;
};

export const avatarStudioTemplates: AvatarStudioTemplate[] = [
  {
    id: "product-host-zh",
    name: {
      zh: "产品介绍主持人",
      en: "Product Host",
      ja: "商品紹介ホスト",
      ko: "제품 소개 진행자",
      es: "Presentador de producto",
      fr: "Presentateur produit",
      ru: "Ведущий продукта",
    },
    thumbnailUrl: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=900&q=80",
    language: "zh",
    scene: "product",
    isFree: true,
    videoUrl: null,
  },
  {
    id: "sales-presenter",
    name: {
      zh: "销售转化口播",
      en: "Sales Presenter",
      ja: "販売向けプレゼンター",
      ko: "세일즈 발표자",
      es: "Presentador de ventas",
      fr: "Presentateur commercial",
      ru: "Продавец-презентер",
    },
    thumbnailUrl: "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=900&q=80",
    language: "multi",
    scene: "sales",
    isFree: true,
    videoUrl: null,
  },
  {
    id: "tutorial-coach",
    name: {
      zh: "教程讲解模板",
      en: "Tutorial Coach",
      ja: "チュートリアル講師",
      ko: "튜토리얼 코치",
      es: "Guia tutorial",
      fr: "Coach tutoriel",
      ru: "Наставник для уроков",
    },
    thumbnailUrl: "https://images.unsplash.com/photo-1543269865-cbf427effbad?auto=format&fit=crop&w=900&q=80",
    language: "multi",
    scene: "tutorial",
    isFree: false,
    videoUrl: null,
  },
];

export function findAvatarStudioTemplate(id?: string | null) {
  if (!id) return null;
  return avatarStudioTemplates.find((template) => template.id === id) ?? null;
}

export function sceneLabel(scene: AvatarStudioTemplate["scene"], locale: keyof AvatarStudioTemplate["name"]) {
  const labels = {
    zh: {
      product: "产品介绍",
      talking: "口播",
      sales: "销售",
      tutorial: "教程",
    },
    en: {
      product: "Product",
      talking: "Talking",
      sales: "Sales",
      tutorial: "Tutorial",
    },
    ja: {
      product: "商品紹介",
      talking: "トーク",
      sales: "販売",
      tutorial: "チュートリアル",
    },
    ko: {
      product: "제품 소개",
      talking: "말하기",
      sales: "세일즈",
      tutorial: "튜토리얼",
    },
    es: {
      product: "Producto",
      talking: "Presentacion",
      sales: "Ventas",
      tutorial: "Tutorial",
    },
    fr: {
      product: "Produit",
      talking: "Presentation",
      sales: "Vente",
      tutorial: "Tutoriel",
    },
    ru: {
      product: "Продукт",
      talking: "Речь",
      sales: "Продажи",
      tutorial: "Урок",
    },
  };
  return labels[locale][scene];
}
