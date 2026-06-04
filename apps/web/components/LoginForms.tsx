"use client";

import { useActionState, useEffect } from "react";
import { Chrome, Mail } from "lucide-react";

import { signInAction, signInWithGoogleAction, signUpAction } from "@/app/actions/auth";
import { useLanguage } from "@/components/LanguageProvider";
import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";

const initialState = { ok: false, message: "" };

const copy = {
  zh: {
    loginTitle: "登录",
    loginBody: "登录后创建视频任务、查看历史任务和额度。",
    signupTitle: "注册",
    signupBody: "Free 套餐每月 3 次生成，适合先跑通数字人口播工作流。",
    email: "邮箱",
    password: "密码",
    newPassword: "设置密码（至少 6 位）",
    emailLogin: "邮箱登录",
    createAccount: "创建账户",
    google: "使用 Google 继续",
  },
  en: {
    loginTitle: "Sign in",
    loginBody: "Create video tasks, view history, and manage credits after signing in.",
    signupTitle: "Create account",
    signupBody: "The Free plan includes 3 generations per month for testing the avatar workflow.",
    email: "Email",
    password: "Password",
    newPassword: "Set password (at least 6 characters)",
    emailLogin: "Sign in with email",
    createAccount: "Create account",
    google: "Continue with Google",
  },
};

export function LoginForms({ next }: { next: string }) {
  const { locale } = useLanguage();
  const current = copy[locale];
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
        <h2 className="text-xl font-semibold text-white">{current.loginTitle}</h2>
        <p className="mt-2 text-sm text-slate-400">{current.loginBody}</p>
        <div className="mt-5 space-y-4">
          <input name="email" type="email" required placeholder={current.email} className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          <input name="password" type="password" required minLength={6} placeholder={current.password} className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          {loginState.message ? <p className={loginState.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{loginState.message}</p> : null}
          <Button type="submit" className="w-full">
            <Mail size={16} />
            {current.emailLogin}
          </Button>
        </div>
      </form>

      <form action={signupAction} className="rounded-lg border border-white/10 bg-panel/80 p-5">
        <input type="hidden" name="next" value={next} />
        <h2 className="text-xl font-semibold text-white">{current.signupTitle}</h2>
        <p className="mt-2 text-sm text-slate-400">{current.signupBody}</p>
        <div className="mt-5 space-y-4">
          <input name="email" type="email" required placeholder={current.email} className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          <input name="password" type="password" required minLength={6} placeholder={current.newPassword} className="h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 outline-none ring-cyan/40 focus:ring-2" />
          {signupState.message ? <p className={signupState.ok ? "text-sm text-lime" : "text-sm text-rose-200"}>{signupState.message}</p> : null}
          <Button type="submit" variant="outline" className="w-full">
            {current.createAccount}
          </Button>
        </div>
      </form>

      <form action={signInWithGoogleAction} className="rounded-lg border border-white/10 bg-panel/80 p-5 lg:col-span-2">
        <input type="hidden" name="next" value={next} />
        <Button type="submit" variant="outline" className="w-full">
          <Chrome size={16} />
          {current.google}
        </Button>
      </form>
    </div>
  );
}
