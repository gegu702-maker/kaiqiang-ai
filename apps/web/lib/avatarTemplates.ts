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
