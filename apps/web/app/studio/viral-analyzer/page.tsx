import { redirect } from "next/navigation";

import { ViralAnalyzerClient } from "@/components/ViralAnalyzerClient";
import { createClient } from "@/lib/supabase/server";

export default async function ViralAnalyzerPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login?next=/studio/viral-analyzer&reason=session_invalid");
  }

  return <ViralAnalyzerClient />;
}
