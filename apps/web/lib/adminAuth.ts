import { redirect } from "next/navigation";

import { isAdminEmail } from "@/lib/admin";
import { createClient } from "@/lib/supabase/server";

export async function requireAdmin(nextPath: string) {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect(`/login?next=${nextPath}`);
  }
  if (!isAdminEmail(session.user.email)) {
    redirect("/account");
  }
  return session.user;
}
