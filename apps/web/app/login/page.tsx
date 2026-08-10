import { redirect } from "next/navigation";

import { LoginForms } from "@/components/LoginForms";
import { createClient } from "@/lib/supabase/server";

type LoginPageProps = {
  searchParams?: Promise<{ next?: string; reason?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const next = sanitizeNext(params?.next ?? "");
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    redirect(next);
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm text-cyan">AI Video Agent Account</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">登录 kaiqiang.ai</h1>
        <p className="mt-3 text-slate-400">账户系统使用 Supabase Auth。后续可在 Supabase 控制台开启 Google OAuth。</p>
        {params?.reason === "project_mismatch" || params?.reason === "session_invalid" ? (
          <p className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100" role="alert">
            当前登录状态不属于此 Preview 环境或已失效，请重新登录 Preview 后继续。
          </p>
        ) : null}
      </div>
      <LoginForms next={next} />
    </main>
  );
}

function sanitizeNext(next: string) {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/account";
  }
  return next;
}
