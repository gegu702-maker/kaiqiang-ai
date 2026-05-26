"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { createClient } from "@/lib/supabase/client";
import { identifyUser, trackEvent } from "@/lib/analytics";

const trackedPages = new Set(["/", "/studio", "/account", "/pricing", "/login"]);

export function AnalyticsRouteEvents() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (trackedPages.has(pathname)) {
      trackEvent("page_view", { path: pathname });
    }
    if (pathname === "/studio") {
      trackEvent("open_studio", { path: pathname });
    }
  }, [pathname]);

  useEffect(() => {
    const analytics = searchParams.get("analytics");
    if (analytics === "login_success") {
      trackEvent("login_success", { path: pathname });
      const params = new URLSearchParams(searchParams.toString());
      params.delete("analytics");
      const nextUrl = params.toString() ? `${pathname}?${params.toString()}` : pathname;
      router.replace(nextUrl, { scroll: false });
    }
  }, [pathname, router, searchParams]);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) {
        identifyUser(data.user.id, data.user.email);
      }
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        identifyUser(session.user.id, session.user.email);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  return null;
}
