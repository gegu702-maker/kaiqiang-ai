export const PRODUCTION_SUPABASE_MEDIA_HOSTNAME = "povfvhdnrpytxbbyndit.supabase.co";
export const PRODUCTION_SUPABASE_MEDIA_ORIGIN = `https://${PRODUCTION_SUPABASE_MEDIA_HOSTNAME}`;

export const isPreviewEnvironment =
  process.env.NEXT_PUBLIC_APP_ENVIRONMENT === "preview";

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
    if (parsed.hostname.toLowerCase() === PRODUCTION_SUPABASE_MEDIA_HOSTNAME) {
      return undefined;
    }
    return value;
  } catch {
    return undefined;
  }
}
