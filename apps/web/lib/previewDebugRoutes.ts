export const PREVIEW_DEBUG_ROUTE_DISABLED_DETAIL = {
  code: "preview_debug_route_disabled",
  message: "This debug route is disabled in the Preview environment.",
} as const;

export function previewDebugRoutesDisabled(
  environment = process.env.NEXT_PUBLIC_APP_ENVIRONMENT,
): boolean {
  return environment?.trim().toLowerCase() === "preview";
}
