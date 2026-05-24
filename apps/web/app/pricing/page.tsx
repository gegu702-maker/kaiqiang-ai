import Link from "next/link";
import { CheckCircle2 } from "lucide-react";

import { PlanCheckoutButton } from "@/components/PlanCheckoutButton";

const plans = [
  {
    name: "Free",
    priceCny: "¥0",
    priceUsd: "$0",
    quota: "每月 3 次生成",
    desc: "适合验证商品视频工作流",
    cta: "免费开始",
  },
  {
    name: "Plus",
    priceCny: "¥199/月",
    priceUsd: "$29/mo",
    quota: "每月 100 次生成",
    desc: "去水印、优先队列，适合稳定测试带货账号",
  },
  {
    name: "Pro",
    priceCny: "¥799/月",
    priceUsd: "$109/mo",
    quota: "每月 1000 次生成",
    desc: "支持声音克隆、上传声音训练、API 权限预留",
  },
  {
    name: "Business",
    priceCny: "定制",
    priceUsd: "Custom",
    quota: "自定义额度",
    desc: "企业级 AI 视频生成、并发和商用支持",
  },
];

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm text-cyan">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">AI 带货视频生成套餐</h1>
        <p className="mt-3 text-slate-400">
          当前阶段先上线额度、订单和支付接口抽象。默认人民币价格，海外支付预留 Stripe / PayPal。
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map((plan) => (
          <section key={plan.name} className="rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow">
            <h2 className="text-2xl font-semibold text-white">{plan.name}</h2>
            <div className="mt-4 flex items-end gap-3">
              <span className="text-4xl font-semibold text-cyan">{plan.priceCny}</span>
              <span className="pb-1 text-sm text-slate-500">{plan.priceUsd}</span>
            </div>
            <p className="mt-3 text-slate-300">{plan.quota}</p>
            <p className="mt-2 text-sm text-slate-500">{plan.desc}</p>
            <ul className="mt-5 space-y-3 text-sm text-slate-300">
              {[
                "AI 卖点分析 / DeepSeek 文案",
                "自动脚本、分镜、封面 Prompt",
                plan.name === "Pro" || plan.name === "Business" ? "AI 声音克隆 / 专属数字人声音" : "Plus 暂不支持声音克隆",
                "FFmpeg 自动合成 MP4",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-lime" />
                  {item}
                </li>
              ))}
            </ul>
            {plan.name === "Free" ? (
              <Link
                href="/login"
                className="mt-6 flex h-11 items-center justify-center rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90"
              >
                {plan.cta}
              </Link>
            ) : (
              <PlanCheckoutButton plan={plan.name === "Plus" ? "plus" : plan.name === "Pro" ? "pro" : "business"} />
            )}
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.04] p-5 text-sm text-slate-400">
        支付引擎已预留：国内 provider 包括微信支付、支付宝、Ping++、易支付、虎皮椒；海外 provider 包括 Stripe、PayPal。
        第一阶段按钮只创建占位订单，不接真实收款。
      </div>
    </main>
  );
}
