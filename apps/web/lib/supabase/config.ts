const SUPABASE_PROJECT_REF_RE = /^[a-z0-9]{20}$/;
const SUPABASE_AUTH_COOKIE_RE = /^sb-([a-z0-9]{20})-auth-token(?:\.\d+)?$/;

export function getSupabaseProjectRef(url: string): string {
  const hostname = new URL(url).hostname.toLowerCase();
  const [projectRef, ...rest] = hostname.split(".");
  if (!SUPABASE_PROJECT_REF_RE.test(projectRef) || rest.join(".") !== "supabase.co") {
    throw new Error("Invalid Supabase project URL.");
  }
  return projectRef;
}

export function getSupabaseAuthStorageKey(url: string): string {
  return `sb-${getSupabaseProjectRef(url)}-auth-token`;
}

export function getSupabaseAuthProjectRefFromStorageName(name: string): string | null {
  return SUPABASE_AUTH_COOKIE_RE.exec(name)?.[1] ?? null;
}

export function isSupabaseAuthStorageName(name: string): boolean {
  return SUPABASE_AUTH_COOKIE_RE.test(name);
}

export function isExpectedSupabaseAuthStorageName(name: string, expectedProjectRef: string): boolean {
  return getSupabaseAuthProjectRefFromStorageName(name) === expectedProjectRef;
}

export function getForeignSupabaseAuthStorageNames(names: Iterable<string>, expectedProjectRef: string): string[] {
  return [...names].filter(
    (name) => isSupabaseAuthStorageName(name) && !isExpectedSupabaseAuthStorageName(name, expectedProjectRef),
  );
}
