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
  ja: {
    loginTitle: "ログイン",
    loginBody: "ログインすると動画タスクの作成、履歴確認、クレジット管理ができます。",
    signupTitle: "アカウント作成",
    signupBody: "Free プランは月 3 回生成でき、アバター動画ワークフローの検証に最適です。",
    email: "メール",
    password: "パスワード",
    newPassword: "パスワードを設定（6文字以上）",
    emailLogin: "メールでログイン",
    createAccount: "アカウント作成",
    google: "Google で続行",
  },
  ko: {
    loginTitle: "로그인",
    loginBody: "로그인 후 영상 작업 생성, 기록 확인, 크레딧 관리를 할 수 있습니다.",
    signupTitle: "계정 만들기",
    signupBody: "Free 플랜은 월 3회 생성을 제공해 아바타 영상 워크플로우 검증에 적합합니다.",
    email: "이메일",
    password: "비밀번호",
    newPassword: "비밀번호 설정(최소 6자)",
    emailLogin: "이메일로 로그인",
    createAccount: "계정 만들기",
    google: "Google로 계속",
  },
  es: {
    loginTitle: "Iniciar sesion",
    loginBody: "Inicia sesion para crear tareas de video, ver el historial y gestionar creditos.",
    signupTitle: "Crear cuenta",
    signupBody: "El plan Free incluye 3 generaciones al mes para probar el flujo de avatar.",
    email: "Email",
    password: "Contrasena",
    newPassword: "Define una contrasena (minimo 6 caracteres)",
    emailLogin: "Entrar con email",
    createAccount: "Crear cuenta",
    google: "Continuar con Google",
  },
  fr: {
    loginTitle: "Connexion",
    loginBody: "Connectez-vous pour creer des videos, consulter l'historique et gerer les credits.",
    signupTitle: "Creer un compte",
    signupBody: "Le plan Free inclut 3 generations par mois pour tester le flux avatar.",
    email: "Email",
    password: "Mot de passe",
    newPassword: "Definir le mot de passe (6 caracteres minimum)",
    emailLogin: "Connexion par email",
    createAccount: "Creer un compte",
    google: "Continuer avec Google",
  },
  ru: {
    loginTitle: "Войти",
    loginBody: "После входа можно создавать видео, смотреть историю и управлять лимитами.",
    signupTitle: "Создать аккаунт",
    signupBody: "Тариф Free дает 3 генерации в месяц для проверки аватарного процесса.",
    email: "Email",
    password: "Пароль",
    newPassword: "Задайте пароль (минимум 6 символов)",
    emailLogin: "Войти по email",
    createAccount: "Создать аккаунт",
    google: "Продолжить с Google",
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
