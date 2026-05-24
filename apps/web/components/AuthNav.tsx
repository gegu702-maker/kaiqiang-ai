import Link from "next/link";
import { LogOut, UserCircle } from "lucide-react";

import { signOutAction } from "@/app/actions/auth";
import { getCurrentUser } from "@/lib/supabase/server";

export async function AuthNav() {
  const user = await getCurrentUser();

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Link className="rounded-md px-3 py-2 hover:bg-white/10" href="/pricing">
          价格
        </Link>
        <Link className="rounded-md px-3 py-2 hover:bg-white/10" href="/login">
          登录 / 注册
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Link className="hidden rounded-md px-3 py-2 hover:bg-white/10 sm:inline-flex" href="/pricing">
        价格
      </Link>
      <Link className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10" href="/account">
        <UserCircle size={16} />
        <span className="hidden max-w-[180px] truncate sm:inline">{user.email}</span>
        <span className="sm:hidden">账户</span>
      </Link>
      <form action={signOutAction}>
        <button className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10" type="submit">
          <LogOut size={16} />
          退出
        </button>
      </form>
    </div>
  );
}
