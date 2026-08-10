"use client";

import { createBrowserClient } from "@supabase/ssr";

import { getSupabaseAuthStorageKey, getSupabaseProjectRef } from "./config";
import { clearForeignSupabaseBrowserState } from "./sessionGuard";

export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error("Missing Supabase browser environment variables.");
  }

  const projectRef = getSupabaseProjectRef(url);
  if (process.env.NEXT_PUBLIC_APP_ENVIRONMENT === "preview") {
    clearForeignSupabaseBrowserState(projectRef);
  }
  return createBrowserClient(url, anonKey, {
    cookieOptions: { name: getSupabaseAuthStorageKey(url) },
  });
}
