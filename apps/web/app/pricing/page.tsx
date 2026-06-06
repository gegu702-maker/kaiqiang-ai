import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { PlanCheckoutButton } from "@/components/PlanCheckoutButton";
import { PricingContactSection } from "@/components/PricingContactSection";

const plans = [
  {
    name: "Free",
    code: "free",
    price: "¥0",
    quota: "每月 3 次生成",
    desc: "适合首次体验和验证数字人口播效果。",
    features: ["每月 3 次生成额度", "上传人物视频和音频", "生成 MP4 成片", "基础历史记录"],
  },
  {
    name: "Creator",
    code: "plus",
    price: "¥199/月",
    quota: "适合稳定创作",
    desc: "适合个人创作者、小团队和电商账号持续制作口播素材。",
    features: ["更多月度生成额度", "优先排队预留", "公开视频下载链接", "适合短视频和商品讲解"],
    badge: "推荐",
  },
  {
    name: "Business",
    code: "business",
    price: "联系商务",
    quota: "团队与高频使用",
    desc: "适合企业内容团队、培训、电商矩阵和定制数字人项目。",
    features: ["自定义生成额度", "声音克隆与模板支持", "团队/API 能力预留", "商务授权与交付支持"],
  },
] as const;

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm font-medium text-cyan">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">AI 数字人口播 SaaS 套餐</h1>
        <p className="mt-3 text-slate-400">
          从免费验证到稳定创作，再到企业级数字人口播生产。当前阶段先完成套餐展示和订单预留，不接入在线支付。
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
        商业化准备：Creator 可作为首个自助套餐，Business 保留人工沟通和定制额度。在线支付接入前，升级按钮仅创建待处理订单或引导联系。
      </div>

      <PricingContactSection />
    </main>
  );
}
