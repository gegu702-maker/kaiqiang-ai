import { ArrowRight, BadgeCheck, Clock } from "lucide-react";
import Link from "next/link";

import { avatarStudioTemplates, sceneLabel } from "@/lib/avatarTemplates";

const copy = {
  title: "Avatar 模板库",
  subtitle: "先用官方模板降低上传门槛。当前模板视频陆续接入中，已上线后可直接带入 Avatar Studio。",
  free: "免费",
  paid: "套餐内",
  comingSoon: "模板视频即将上线",
  useTemplate: "选择模板",
};

export default function AvatarTemplatesPage() {
  return (
    <main className="min-h-[calc(100vh-86px)] bg-slate-50 px-4 py-10 text-slate-950 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-7">
          <p className="text-sm font-medium text-blue-700">Templates</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{copy.title}</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">{copy.subtitle}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {avatarStudioTemplates.map((template) => (
            <article key={template.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div
                className="aspect-video w-full bg-cover bg-center"
                style={{ backgroundImage: `url(${template.thumbnailUrl})` }}
                aria-label={template.name.zh}
              />
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">{template.name.zh}</h2>
                    <p className="mt-1 text-sm text-slate-500">{template.name.en}</p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                    <BadgeCheck size={13} />
                    {template.isFree ? copy.free : copy.paid}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-600">
                  <span className="rounded-md bg-slate-100 px-2 py-1">{sceneLabel(template.scene, "zh")}</span>
                  <span className="rounded-md bg-slate-100 px-2 py-1">{template.language.toUpperCase()}</span>
                </div>
                {!template.videoUrl ? (
                  <p className="mt-4 inline-flex items-center gap-2 text-sm text-amber-700">
                    <Clock size={15} />
                    {copy.comingSoon}
                  </p>
                ) : null}
                <Link
                  href={`/studio/avatar?template=${template.id}`}
                  className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500"
                >
                  {copy.useTemplate}
                  <ArrowRight size={16} />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
