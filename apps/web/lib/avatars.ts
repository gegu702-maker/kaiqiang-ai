import { avatarTemplates } from "@/lib/avatarTemplates";

export type AvatarProfile = {
  id: string;
  name: string;
  label: string;
  accent: string;
  initials: string;
};

export const avatarProfiles: AvatarProfile[] = [
  ...avatarTemplates.map((template) => ({
    id: template.id,
    name: template.name,
    label: template.description,
    accent: template.gender === "male" ? "from-blue-300/70 to-lime/70" : template.style === "tech" ? "from-violet-300/70 to-cyan/70" : "from-cyan/70 to-lime/70",
    initials: template.gender === "male" ? "男" : "女",
  })),
  {
    id: "emily",
    name: "Emily",
    label: "英文女主播",
    accent: "from-cyan/70 to-fuchsia-300/70",
    initials: "EM",
  },
  {
    id: "david",
    name: "David",
    label: "英文男主播",
    accent: "from-blue-300/70 to-lime/70",
    initials: "DV",
  },
  {
    id: "sophia",
    name: "Sophia",
    label: "中文女主播",
    accent: "from-lime/70 to-cyan/70",
    initials: "SO",
  },
  {
    id: "alex",
    name: "Alex",
    label: "科技风主播",
    accent: "from-violet-300/70 to-cyan/70",
    initials: "AX",
  },
  {
    id: "heygen_custom",
    name: "HeyGen Custom",
    label: "用户形象素材",
    accent: "from-cyan/70 to-lime/70",
    initials: "HG",
  },
];

export function getAvatarProfile(id: string) {
  return avatarProfiles.find((avatar) => avatar.id === id) ?? avatarProfiles[2];
}
