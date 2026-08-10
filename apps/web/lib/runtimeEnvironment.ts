export const isPreviewEnvironment =
  process.env.NEXT_PUBLIC_APP_ENVIRONMENT === "preview";

// The Production media origin is compiled out of Preview builds. Production
// behavior stays unchanged, while Preview bundles contain no Production ref.
export const PRODUCTION_SUPABASE_MEDIA_HOSTNAME = isPreviewEnvironment
  ? ""
  : "povfvhdnrpytxbbyndit.supabase.co";
export const PRODUCTION_SUPABASE_MEDIA_ORIGIN = PRODUCTION_SUPABASE_MEDIA_HOSTNAME
  ? `https://${PRODUCTION_SUPABASE_MEDIA_HOSTNAME}`
  : "";

function configuredSupabaseHostname(): string {
  try {
    return new URL(process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").hostname.toLowerCase();
  } catch {
    return "";
  }
}

export function allowExternalMediaUrl(
  url: string | undefined,
  previewEnvironment = isPreviewEnvironment,
): string | undefined {
  const value = url?.trim();
  if (!value) {
    return undefined;
  }

  if (!previewEnvironment) {
    return value;
  }

  if (value.startsWith("/") && !value.startsWith("//")) {
    return value;
  }

  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:") {
      return undefined;
    }
    const hostname = parsed.hostname.toLowerCase();
    if (hostname.endsWith(".supabase.co") && hostname !== configuredSupabaseHostname()) {
      return undefined;
    }
    return value;
  } catch {
    return undefined;
  }
}
