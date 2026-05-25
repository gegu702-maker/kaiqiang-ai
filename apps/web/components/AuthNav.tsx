import Link from "next/link";
import { LogOut } from "lucide-react";

import { signOutAction } from "@/app/actions/auth";
import { HeaderAuthLabel } from "@/components/HeaderAuthLabel";
import { HeaderLogoutLabel, HeaderUserMenu } from "@/components/HeaderUserMenu";
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
