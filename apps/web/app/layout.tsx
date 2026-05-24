import type { Metadata } from "next";
import Link from "next/link";
import { Inter } from "next/font/google";
import { Clapperboard } from "lucide-react";

import { AuthNav } from "@/components/AuthNav";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "kaiqiang.ai - AI Video Agent Studio",
  description: "AI 带货视频脚本、分镜和半自动交付工作流平台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.className} antialiased`}>
        <div className="min-h-screen">
          <header className="border-b border-white/10 bg-ink/70 backdrop-blur">
            <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
              <Link href="/" className="flex items-center gap-3 font-semibold tracking-wide">
                <span className="grid size-9 place-items-center rounded-lg border border-cyan/30 bg-cyan/10 text-cyan shadow-glow">
                  <Clapperboard size={18} />
                </span>
                Avatar Studio
              </Link>
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Link className="rounded-md px-3 py-2 hover:bg-white/10" href="/tasks">
                  我的任务
                </Link>
                <Link className="rounded-md px-3 py-2 hover:bg-white/10" href="/admin">
                  管理后台
                </Link>
                <AuthNav />
              </div>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
