"use client";

import posthog from "posthog-js";

export type AnalyticsProperties = Record<string, string | number | boolean | null | undefined>;

export function isAnalyticsEnabled() {
  return process.env.NODE_ENV === "production" && Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY);
}

export function trackEvent(name: string, properties?: AnalyticsProperties) {
  if (!isAnalyticsEnabled()) return;
  posthog.capture(name, properties);
}

export function identifyUser(userId: string, email?: string | null) {
  if (!isAnalyticsEnabled()) return;
  posthog.identify(userId, email ? { email } : undefined);
}
