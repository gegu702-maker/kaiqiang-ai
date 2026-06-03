export type AvatarTemplate = {
  id: string;
  name: string;
  description: string;
  avatar_image: string;
  voice_type: "BV001_streaming" | "BV002_streaming";
  gender: "female" | "male";
  style: "business" | "tech";
  vip_only: boolean;
};

export const avatarTemplates: AvatarTemplate[] = [
  {
    id: "business_female_01",
    name: "商务女主播",
    description: "适合知识口播、课程介绍、商业内容",
    avatar_image: "/avatars/business_female_01.png",
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

export function getAvatarTemplate(id: string | null | undefined) {
  return avatarTemplates.find((template) => template.id === id) ?? avatarTemplates[0];
}

export type AvatarStudioTemplate = {
  id: string;
  name: {
    zh: string;
    en: string;
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
    name: { zh: "产品介绍主持人", en: "Product Host" },
    thumbnailUrl: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=900&q=80",
    language: "zh",
    scene: "product",
    isFree: true,
    videoUrl: null,
  },
  {
    id: "sales-presenter",
    name: { zh: "销售转化口播", en: "Sales Presenter" },
    thumbnailUrl: "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=900&q=80",
    language: "multi",
    scene: "sales",
    isFree: true,
    videoUrl: null,
  },
  {
    id: "tutorial-coach",
    name: { zh: "教程讲解模板", en: "Tutorial Coach" },
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

export function sceneLabel(scene: AvatarStudioTemplate["scene"], locale: "zh" | "en") {
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
  };
  return labels[locale][scene];
}
