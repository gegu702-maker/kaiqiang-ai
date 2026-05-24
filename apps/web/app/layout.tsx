import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AuthNav } from "@/components/AuthNav";
import { LanguageProvider } from "@/components/LanguageProvider";
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
        <LanguageProvider>
          <div className="min-h-screen">
            <SiteHeader authSlot={<AuthNav />} />
            {children}
          </div>
        </LanguageProvider>
      </body>
    </html>
  );
}
