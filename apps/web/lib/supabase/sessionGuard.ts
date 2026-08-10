import { getSupabaseProjectRef } from "./config";

type JwtClaims = {
  aud?: string | string[];
  exp?: number;
  iss?: string;
};

type SessionLike = {
  access_token: string;
};

export type SessionGuardAuth = {
  getSession(): Promise<{ data: { session: SessionLike | null }; error?: unknown }>;
  refreshSession(): Promise<{ data: { session: SessionLike | null }; error?: unknown }>;
  getUser(accessToken: string): Promise<{ data: { user: unknown | null }; error?: unknown }>;
};

export type PreviewSessionFailureReason =
  | "missing_session"
  | "project_mismatch"
  | "invalid_token"
  | "refresh_failed"
  | "user_validation_failed";

export class PreviewSessionError extends Error {
  constructor(public readonly reason: PreviewSessionFailureReason) {
    super("登录状态与当前 Preview 环境不匹配或已失效，请重新登录 Preview。");
    this.name = "PreviewSessionError";
  }
}

function decodeBase64UrlJson(value: string): JwtClaims | null {
  try {
    const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const json = decodeURIComponent(
      Array.from(atob(padded), (character) => `%${character.charCodeAt(0).toString(16).padStart(2, "0")}`).join(""),
    );
    return JSON.parse(json) as JwtClaims;
  } catch {
    return null;
  }
}

export function inspectSupabaseAccessToken(
  accessToken: string,
  expectedSupabaseUrl: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): { valid: boolean; expired: boolean; projectRef: string | null; reason?: PreviewSessionFailureReason } {
  const parts = accessToken.split(".");
  const claims = parts.length === 3 ? decodeBase64UrlJson(parts[1]) : null;
  if (!claims || typeof claims.iss !== "string" || typeof claims.exp !== "number") {
    return { valid: false, expired: false, projectRef: null, reason: "invalid_token" };
  }

  let issuer: URL;
  try {
    issuer = new URL(claims.iss);
  } catch {
    return { valid: false, expired: false, projectRef: null, reason: "invalid_token" };
  }

  const projectRef = issuer.hostname.split(".")[0] || null;
  const expectedProjectRef = getSupabaseProjectRef(expectedSupabaseUrl);
  const expectedIssuer = `${expectedSupabaseUrl.replace(/\/$/, "")}/auth/v1`;
  const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  const projectMatches = projectRef === expectedProjectRef && claims.iss.replace(/\/$/, "") === expectedIssuer;
  if (!projectMatches) {
    return { valid: false, expired: claims.exp <= nowSeconds, projectRef, reason: "project_mismatch" };
  }
  if (!audience.includes("authenticated")) {
    return { valid: false, expired: claims.exp <= nowSeconds, projectRef, reason: "invalid_token" };
  }
  const expired = claims.exp <= nowSeconds;
  return { valid: !expired, expired, projectRef, reason: expired ? "refresh_failed" : undefined };
}

export async function getVerifiedSupabaseAccessToken(
  auth: SessionGuardAuth,
  expectedSupabaseUrl: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<string> {
  const initial = await auth.getSession();
  let session = initial.data.session;
  if (!session?.access_token) throw new PreviewSessionError("missing_session");

  let inspection = inspectSupabaseAccessToken(session.access_token, expectedSupabaseUrl, nowSeconds);
  if (inspection.reason === "project_mismatch" || inspection.reason === "invalid_token") {
    throw new PreviewSessionError(inspection.reason);
  }

  if (inspection.expired) {
    const refreshed = await auth.refreshSession();
    session = refreshed.data.session;
    if (refreshed.error || !session?.access_token) throw new PreviewSessionError("refresh_failed");
    inspection = inspectSupabaseAccessToken(session.access_token, expectedSupabaseUrl, nowSeconds);
    if (!inspection.valid) throw new PreviewSessionError(inspection.reason ?? "refresh_failed");
  }

  const userResult = await auth.getUser(session.access_token);
  if (userResult.error || !userResult.data.user) throw new PreviewSessionError("user_validation_failed");
  return session.access_token;
}

export function clearForeignSupabaseBrowserState(expectedProjectRef: string): string[] {
  if (typeof window === "undefined" || typeof document === "undefined") return [];
  const removed = new Set<string>();
  const localStorageNames = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index))
    .filter((name): name is string => Boolean(name));
  for (const name of localStorageNames) {
    if (/^sb-[a-z0-9]{20}-auth-token(?:-code-verifier)?$/.test(name) && !name.startsWith(`sb-${expectedProjectRef}-`)) {
      window.localStorage.removeItem(name);
      removed.add(name);
    }
    if (name.startsWith("viral-analysis-job:") && !name.startsWith(`viral-analysis-job:${expectedProjectRef}:`)) {
      window.localStorage.removeItem(name);
      removed.add(name);
    }
  }

  const cookieNames = document.cookie
    .split(";")
    .map((part) => part.trim().split("=", 1)[0])
    .filter(Boolean);
  for (const name of cookieNames) {
    if (/^sb-[a-z0-9]{20}-auth-token(?:\.\d+)?$/.test(name) && !name.startsWith(`sb-${expectedProjectRef}-`)) {
      document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
      removed.add(name);
    }
  }
  return [...removed];
}

export function clearCurrentSupabaseBrowserState(expectedProjectRef: string): void {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const base = `sb-${expectedProjectRef}-auth-token`;
  window.localStorage.removeItem(base);
  window.localStorage.removeItem(`${base}-code-verifier`);
  for (const name of [base, ...Array.from({ length: 8 }, (_, index) => `${base}.${index}`)]) {
    document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
  }
}
