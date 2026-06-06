import Link from "next/link";
import { LogOut } from "lucide-react";

import { signOutAction } from "@/app/actions/auth";
import { HeaderAuthLabel } from "@/components/HeaderAuthLabel";
import { HeaderLogoutLabel, HeaderUserMenu } from "@/components/HeaderUserMenu";
import { isAdminEmail } from "@/lib/admin";
import { getCurrentUser } from "@/lib/supabase/server";

export async function AuthNav() {
  const user = await getCurrentUser();

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Link className="rounded-md px-3 py-2 hover:bg-white/10" href="/login" title="Login">
          <HeaderAuthLabel />
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {isAdminEmail(user.email) ? (
        <Link className="hidden rounded-md px-3 py-2 text-cyan hover:bg-white/10 sm:inline-flex" href="/admin">
          Admin
        </Link>
      ) : null}
      <HeaderUserMenu email={user.email ?? ""} />
      <form action={signOutAction}>
        <button className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10" type="submit">
          <LogOut size={16} />
          <HeaderLogoutLabel />
        </button>
      </form>
    </div>
  );
}
