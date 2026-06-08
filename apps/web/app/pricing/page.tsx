import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { PlanCheckoutButton } from "@/components/PlanCheckoutButton";
import { PricingContactSection } from "@/components/PricingContactSection";

const plans = [
  {
    name: "Free",
    code: "free",
    price: "¥0",
    quota: "每月 3 次体验",
    desc: "适合首次验证爆款链接拆解、AI 仿写和数字人口播生成效果。",
    features: ["每月 3 次数字人口播生成", "爆款链接分析体验", "基础 AI 仿写", "固定数字人模板", "MP4 成片导出"],
  },
  {
    name: "Creator",
    code: "plus",
    price: "¥199/月",
    quota: "稳定内容生产",
    desc: "适合自媒体、电商卖家和知识 IP 持续生产原创口播短视频。",
    features: ["更高月度生成额度", "爆款拆解与原创仿写", "1080P 数字人口播导出", "商务女主播 / 男主播 / AI 女主播", "火山引擎音色与声音试听", "优先生成队列"],
    badge: "推荐",
  },
  {
    name: "Business",
    code: "business",
    price: "联系商务",
    quota: "团队与高频使用",
    desc: "适合企业内容团队、电商矩阵、培训交付和定制数字人项目。",
    features: ["自定义生成额度", "声音克隆与专属 voice_id", "团队/API 能力预留", "专属数字人模板支持", "商务授权与交付支持", "专属客服与实施支持"],
  },
] as const;

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm font-medium text-cyan">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">AI 数字人口播 SaaS 套餐</h1>
        <p className="mt-3 text-slate-400">
          从爆款链接拆解到 AI 仿写，再到数字人口播导出。三档套餐覆盖体验验证、稳定创作和企业级交付。
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map((plan) => (
          <section key={plan.code} className={plan.code === "plus" ? "relative rounded-lg border border-cyan/45 bg-panel/90 p-5 shadow-glow" : "rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow"}>
            {"badge" in plan ? <span className="absolute right-4 top-4 rounded-full bg-cyan px-3 py-1 text-xs font-semibold text-ink">{plan.badge}</span> : null}
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
        Creator 面向持续创作，Business 面向团队、矩阵账号和定制交付。支付接入前，升级按钮用于创建待处理订单或引导商务沟通。
      </div>

      <PricingContactSection />
    </main>
  );
}
