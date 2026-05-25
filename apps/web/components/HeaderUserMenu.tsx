"use client";

import Link from "next/link";
import { UserCircle } from "lucide-react";

import { useLanguage } from "@/components/LanguageProvider";

const copy = {
  zh: {
    account: "账户",
    logout: "退出",
  },
  en: {
    account: "Account",
    logout: "Logout",
  },
};

export function HeaderUserMenu({ email }: { email: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];

  return (
    <Link className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10" href="/account">
      <UserCircle size={16} />
      <span className="hidden max-w-[180px] truncate sm:inline">{email}</span>
      <span className="sm:hidden">{current.account}</span>
    </Link>
  );
}

export function HeaderLogoutLabel() {
  const { locale } = useLanguage();
  return <>{copy[locale].logout}</>;
}
