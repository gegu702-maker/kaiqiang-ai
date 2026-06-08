import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { PricingContactSection } from "@/components/PricingContactSection";

const plans = [
  {
    name: "Free",
    code: "free",
    price: "¥0",
    value: "3 次生成额度",
    desc: "适合首次体验数字人口播效果",
    features: ["每月 3 次生成额度", "上传人物视频", "上传音频配音", "AI 脚本生成", "MP4 导出", "历史记录保存 7 天", "标准生成队列"],
    buttonLabel: "免费开始",
  },
  {
    name: "Creator",
    code: "plus",
    price: "¥199/月",
    value: "1000 积分 ≈ 33 分钟视频",
    desc: "适合自媒体、电商卖家、知识IP持续创作",
    features: ["每月 1000 积分", "约 33 分钟数字人口播", "1080P 高清导出", "去除平台水印", "优先生成队列", "无限历史记录", "商业使用授权", "多语言配音", "专属创作模板库", "批量生成任务"],
    badge: "推荐",
    buttonLabel: "升级 Creator",
  },
  {
    name: "Pro",
    code: "pro",
    price: "¥499/月",
    value: "3000 积分 ≈ 100 分钟视频",
    desc: "适合工作室、矩阵账号、企业培训",
    features: ["包含 Creator 全部权益", "每月 3000 积分", "约 100 分钟数字人口播", "声音克隆", "极速生成队列", "API 调用权限", "多数字人管理", "批量任务生成", "高级 TTS 音色", "优先技术支持"],
    badge: "最受欢迎",
    buttonLabel: "升级 Pro",
  },
  {
    name: "Business",
    code: "business",
    price: "联系商务",
    value: "按需定制",
    desc: "适合企业团队和高频使用场景",
    features: ["包含 Pro 全部权益", "自定义额度", "团队协作", "多成员账号", "API 高额度", "专属数字人定制", "企业培训方案", "私有化部署咨询", "专属客服", "SLA 服务保障"],
    buttonLabel: "联系商务",
  },
] as const;

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8 max-w-3xl">
        <p className="text-sm font-medium text-cyan">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">AI 数字人口播 SaaS 套餐</h1>
        <p className="mt-3 text-slate-400">
          从首次体验到稳定创作，再到团队级数字人口播生产。四层套餐清晰覆盖个人创作者、工作室和企业团队。
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-4">
        {plans.map((plan) => (
          <section key={plan.name} className={plan.code === "plus" ? "relative rounded-lg border border-cyan/45 bg-panel/90 p-5 shadow-glow" : plan.code === "pro" ? "relative rounded-lg border border-lime/35 bg-panel/85 p-5 shadow-glow" : "relative rounded-lg border border-white/10 bg-panel/80 p-5 shadow-glow"}>
            {"badge" in plan ? <span className="absolute right-4 top-4 rounded-full bg-cyan px-3 py-1 text-xs font-semibold text-ink">{plan.badge}</span> : null}
            <h2 className="text-2xl font-semibold text-white">{plan.name}</h2>
            <div className="mt-4">
              <span className="text-4xl font-semibold text-cyan">{plan.price}</span>
              <p className="mt-2 text-sm font-medium text-lime">{plan.value}</p>
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
            <Link
              href={plan.code === "business" ? "#pricing-contact" : "/login?next=/pricing"}
              className="mt-6 flex h-11 items-center justify-center rounded-md bg-cyan px-4 text-sm font-semibold text-ink hover:bg-cyan/90"
            >
              {plan.buttonLabel}
            </Link>
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-white/10 bg-white/[0.04] p-5 text-sm leading-6 text-slate-400">
        Creator 对应稳定创作入门档，Pro 面向需要声音克隆、API 和矩阵管理的高频团队，Business 支持按需定制。
      </div>

      <div id="pricing-contact">
        <PricingContactSection />
      </div>
    </main>
  );
}
