export const navigationCopy = {
  zh: {
    home: "首页",
    pricing: "套餐",
    templates: "模板",
    studio: "Studio",
    account: "账户",
    menu: "菜单",
    language: "语言",
  },
  en: {
    home: "Home",
    pricing: "Pricing",
    templates: "Templates",
    studio: "Studio",
    account: "Account",
    menu: "Menu",
    language: "Language",
  },
} as const;

export const mainNavigationItems = [
  { href: "/", key: "home" },
  { href: "/pricing", key: "pricing" },
  { href: "/studio/templates", key: "templates" },
  { href: "/studio", key: "studio" },
  { href: "/account", key: "account" },
] as const;
