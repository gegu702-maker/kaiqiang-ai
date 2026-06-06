export type CaseLocale = "zh" | "en";

export type CustomerCase = {
  id: string;
  category: "product" | "avatar" | "commerce" | "business";
  title: Record<CaseLocale, string>;
  description: Record<CaseLocale, string>;
  thumbnailUrl: string;
  videoUrl: string;
  language: CaseLocale | "multi";
  featured?: boolean;
};

export const customerCases: CustomerCase[] = [
  {
    id: "product-launch-demo",
    category: "product",
    title: {
      zh: "产品卖点讲解",
      en: "Product Launch Demo",
    },
    description: {
      zh: "上传真人口播素材和产品配音，生成适合首页、广告和社媒投放的数字人口播短片。",
      en: "Upload presenter footage and a voiceover to create a talking avatar clip for landing pages, ads, and social channels.",
    },
    thumbnailUrl: "/avatars/business_female_01.png",
    videoUrl: "",
    language: "multi",
    featured: true,
  },
  {
    id: "ai-avatar-spokesperson",
    category: "avatar",
    title: {
      zh: "AI 数字人口播",
      en: "AI Talking Avatar",
    },
    description: {
      zh: "用一段清晰人物视频驱动自然口型同步，快速验证数字人主持、课程和品牌介绍效果。",
      en: "Use clear person footage to validate digital hosts, course intros, and brand explainers with natural lip sync.",
    },
    thumbnailUrl: "/avatars/ai_female_01.png",
    videoUrl: "",
    language: "multi",
    featured: true,
  },
  {
    id: "ecommerce-short-video",
    category: "commerce",
    title: {
      zh: "电商带货短视频",
      en: "E-commerce Short Video",
    },
    description: {
      zh: "为商品详情页、直播预热视频和投流素材快速生成真人感口播内容。",
      en: "Create human-feeling product narration for PDPs, livestream previews, and performance creatives.",
    },
    thumbnailUrl: "/avatars/business_male_01.png",
    videoUrl: "",
    language: "multi",
  },
  {
    id: "business-training",
    category: "business",
    title: {
      zh: "企业培训说明",
      en: "Business Training",
    },
    description: {
      zh: "将业务汇报、流程说明和培训脚本转成统一风格的视频资产。",
      en: "Turn reports, process explainers, and training scripts into consistent video assets.",
    },
    thumbnailUrl: "/logo-transparent.png",
    videoUrl: "",
    language: "multi",
  },
];

export function getFeaturedCases() {
  return customerCases.filter((item) => item.featured).slice(0, 2);
}
