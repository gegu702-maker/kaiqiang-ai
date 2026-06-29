import { redirect } from "next/navigation";

import { ViralAnalyzerClient } from "@/components/ViralAnalyzerClient";
import { createClient } from "@/lib/supabase/server";

export default async function StudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/studio");
  }

  return <ViralAnalyzerClient />;
}
