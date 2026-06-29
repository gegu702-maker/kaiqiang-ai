import { redirect } from "next/navigation";

import { StudioWorkspace } from "@/components/StudioWorkspace";
import { createClient } from "@/lib/supabase/server";

export default async function StudioPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login?next=/studio");
  }

  return <StudioWorkspace />;
}
