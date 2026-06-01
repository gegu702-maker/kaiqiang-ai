import { redirect } from "next/navigation";

import { AvatarVideoGenerator } from "@/components/AvatarVideoGenerator";
import { createClient } from "@/lib/supabase/server";

export default async function AvatarStudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/studio/avatar");
  }

  return (
    <main className="min-h-[calc(100vh-86px)] bg-slate-50 text-slate-950">
      <AvatarVideoGenerator />
    </main>
  );
}
