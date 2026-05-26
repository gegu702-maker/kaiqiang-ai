import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";

import { AnalyticsRouteEvents } from "@/components/AnalyticsRouteEvents";
import { AuthNav } from "@/components/AuthNav";
import { LanguageProvider } from "@/components/LanguageProvider";
import { PostHogClientProvider } from "@/components/PostHogClientProvider";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "KAIQIANG.AI - AI Content Creation",
  description: "Kaiqiang.ai 专注于数字人、AI 视频生成与创作者工具。",
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
            </div>
          </LanguageProvider>
        </PostHogClientProvider>
      </body>
    </html>
  );
}
