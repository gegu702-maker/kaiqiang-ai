import { redirect } from "next/navigation";

import { AvatarVideoGenerator } from "@/components/AvatarVideoGenerator";
import { createClient } from "@/lib/supabase/server";

export default async function AvatarStudioPage({ searchParams }: { searchParams?: Promise<{ template?: string; script_text?: string }> }) {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/studio/avatar");
  }

  const params = await searchParams;

  return (
    <main className="min-h-[calc(100vh-86px)] bg-slate-50 text-slate-950">
      <AvatarVideoGenerator initialTemplateId={params?.template} initialScriptText={params?.script_text} />
    </main>
  );
}
