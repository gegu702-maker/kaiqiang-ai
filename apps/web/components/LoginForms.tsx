"use client";

import { useActionState, useEffect } from "react";
import { Chrome, Mail } from "lucide-react";

import { signInAction, signUpAction } from "@/app/actions/auth";
import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";

const initialState = { ok: false, message: "" };

export function LoginForms({ next }: { next: string }) {
  const [loginState, loginAction] = useActionState(signInAction, initialState);
  const [signupState, signupAction] = useActionState(signUpAction, initialState);

  useEffect(() => {
    if (signupState.ok) {
      trackEvent("signup_success", { next });
    }
  }, [next, signupState.ok]);

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <form action={loginAction} className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
        <input type="hidden" name="next" value={next} />
        <h2 className="text-xl font-semibold text-white">登录</h2>
        <p className="mt-2 text-sm text-slate-400">登录后创建视频任务、查看历史任务和额度。</p>
        <div className="mt-5 space-y-4">
          <input name="email" type="email" required placeholder="邮箱" className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          <input name="password" type="password" required minLength={6} placeholder="密码" className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          {loginState.message ? <p className={loginState.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{loginState.message}</p> : null}
          <Button type="submit" className="w-full">
            <Mail size={16} />
            邮箱登录
          </Button>
        </div>
      </form>

      <form action={signupAction} className="rounded-lg border border-white/10 bg-panel/80 p-5">
        <input type="hidden" name="next" value={next} />
        <h2 className="text-xl font-semibold text-white">注册</h2>
        <p className="mt-2 text-sm text-slate-400">Free 套餐每月 3 次生成，适合先跑通带货视频工作流。</p>
        <div className="mt-5 space-y-4">
          <input name="email" type="email" required placeholder="邮箱" className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          <input name="password" type="password" required minLength={6} placeholder="设置密码（至少 6 位）" className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          {signupState.message ? <p className={signupState.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{signupState.message}</p> : null}
          <Button type="submit" variant="outline" className="w-full">
            创建账户
          </Button>
          <button
            type="button"
            disabled
            className="flex h-11 w-full items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.03] text-sm text-slate-500"
            title="Google OAuth 已预留，需在 Supabase Auth Providers 中配置 Client ID / Secret 后开启。"
          >
            <Chrome size={16} />
            Google 登录（预留）
          </button>
        </div>
      </form>
    </div>
  );
}
