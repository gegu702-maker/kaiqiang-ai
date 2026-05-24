import { LandingPage } from "@/components/LandingPage";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return <LandingPage startHref={session?.user ? "/studio" : "/login?next=/studio"} />;
}
