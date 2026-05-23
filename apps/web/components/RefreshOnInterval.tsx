"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function RefreshOnInterval({ seconds = 10 }: { seconds?: number }) {
  const router = useRouter();

  useEffect(() => {
    const timer = window.setInterval(() => {
      router.refresh();
    }, seconds * 1000);

    return () => window.clearInterval(timer);
  }, [router, seconds]);

  return null;
}
