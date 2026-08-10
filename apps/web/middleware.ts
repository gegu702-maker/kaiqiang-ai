import { type NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";

import {
  getForeignSupabaseAuthStorageNames,
  getSupabaseAuthStorageKey,
  getSupabaseProjectRef,
  isExpectedSupabaseAuthStorageName,
} from "@/lib/supabase/config";

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    return response;
  }

  const expectedProjectRef = getSupabaseProjectRef(url);
  const requestCookieNames = request.cookies.getAll().map(({ name }) => name);
  const foreignAuthCookieNames = process.env.NEXT_PUBLIC_APP_ENVIRONMENT === "preview"
    ? getForeignSupabaseAuthStorageNames(requestCookieNames, expectedProjectRef)
    : [];

  const supabase = createServerClient(url, anonKey, {
    cookieOptions: { name: getSupabaseAuthStorageKey(url) },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const currentAuthCookieNames = requestCookieNames.filter((name) =>
    isExpectedSupabaseAuthStorageName(name, expectedProjectRef),
  );
  const cookieNamesToClear = new Set([
    ...foreignAuthCookieNames,
    ...(!user ? currentAuthCookieNames : []),
  ]);

  if (!user && request.nextUrl.pathname.startsWith("/studio/viral-analyzer")) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    loginUrl.searchParams.set("reason", foreignAuthCookieNames.length ? "project_mismatch" : "session_invalid");
    response = NextResponse.redirect(loginUrl);
  }

  for (const name of cookieNamesToClear) {
    response.cookies.delete(name);
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
