import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";

import { AnalyticsRouteEvents } from "@/components/AnalyticsRouteEvents";
import { AuthNav } from "@/components/AuthNav";
import { LanguageProvider } from "@/components/LanguageProvider";
import { PostHogClientProvider } from "@/components/PostHogClientProvider";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://kaiqiang.ai"),
  title: {
    default: "Kaiqiang AI - AI Avatar Generator",
    template: "%s | Kaiqiang AI",
  },
  description:
    "Kaiqiang AI is an AI Avatar Generator for AI Talking Avatar videos, AI Video Generator workflows, Digital Human content, and creator tools.",
  keywords: ["AI Avatar Generator", "AI Talking Avatar", "AI Video Generator", "Digital Human", "Kaiqiang AI"],
  openGraph: {
    title: "Kaiqiang AI - AI Avatar Generator",
    description:
      "Create AI talking avatar videos with Kaiqiang AI, a Digital Human and AI Video Generator platform for creators.",
    url: "https://kaiqiang.ai",
    siteName: "Kaiqiang AI",
    images: [
      {
        url: "/logo.png",
        width: 512,
        height: 512,
        alt: "Kaiqiang AI logo",
      },
    ],
    locale: "zh_CN",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Kaiqiang AI - AI Avatar Generator",
    description:
      "AI Talking Avatar, AI Video Generator, and Digital Human tools for creators.",
    images: ["/logo.png"],
  },
  alternates: {
    canonical: "https://kaiqiang.ai",
  },
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.className} antialiased`}>
        <PostHogClientProvider>
          <LanguageProvider>
            <Suspense fallback={null}>
              <AnalyticsRouteEvents />
            </Suspense>
            <div className="min-h-screen">
              <SiteHeader authSlot={<AuthNav />} />
              {children}
              <SiteFooter />
            </div>
          </LanguageProvider>
        </PostHogClientProvider>
      </body>
    </html>
  );
}
