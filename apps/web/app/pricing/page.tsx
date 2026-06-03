import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { PlanCheckoutButton } from "@/components/PlanCheckoutButton";

const plans = [
  {
    name: "Free",
    code: "free",
    price: "¥0",
    quota: "少量生成额度",
    desc: "适合注册后快速验证数字人口播效果。",
    features: ["免费体验额度", "上传人物视频和音频", "生成 MP4 成片"],
  },
  {
    name: "Plus",
    code: "plus",
    price: "¥199/月",
    quota: "更多生成额度",
    desc: "适合开始稳定测试账号内容和转化素材。",
    features: ["更多月度生成额度", "优先排队预留", "公开视频下载链接"],
  },
  {
    name: "Pro",
    code: "pro",
    price: "¥799/月",
    quota: "高级能力预留",
    desc: "适合团队验证声音克隆和高级模板工作流。",
    features: ["包含声音克隆预留", "高级模板预留", "团队/API 能力预留"],
  },
] as const;

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm font-medium text-cyan">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">AI 数字人口播 SaaS 套餐</h1>
        <p className="mt-3 text-slate-400">
          当前阶段先开放用户注册、免费额度、生成消耗和升级订单。支付 provider 已抽象，后续可接 Stripe Checkout、Lemon Squeezy 或 Creem。
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map((plan) => (
          <section key={plan.code} className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-2xl font-semibold text-white">{plan.name}</h2>
            <div className="mt-4 flex items-end gap-3">
              <span className="text-4xl font-semibold text-cyan">{plan.price}</span>
              <span className="pb-1 text-sm text-slate-500">{plan.quota}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">{plan.desc}</p>
            <ul className="mt-5 space-y-3 text-sm text-slate-300">
              {plan.features.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-lime" />
                  {item}
                </li>
              ))}
            </ul>
            {plan.code === "free" ? (
              <Link href="/login" className="mt-6 flex h-11 items-center justify-center rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90">
                免费开始
              </Link>
            ) : (
              <PlanCheckoutButton plan={plan.code} />
            )}
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.04] p-5 text-sm leading-6 text-slate-400">
        支付系统即将开放：当前没有支付密钥时，升级按钮会创建 pending 订单并提示稍后开放；未来配置 provider 密钥后，可跳转托管 checkout。
      </div>
    </main>
  );
}
