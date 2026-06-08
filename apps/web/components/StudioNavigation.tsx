import { Clapperboard, Film, Layers3, LineChart, Sparkles, WandSparkles, type LucideIcon } from "lucide-react";
import Link from "next/link";

const navItems: Array<[string, string, LucideIcon]> = [
  ["Agent", "/studio", WandSparkles],
  ["Viral", "/studio/viral-analyzer", Sparkles],
  ["Script", "/studio", Layers3],
  ["Shots", "/studio/templates", Film],
  ["Render", "/studio/avatar", Clapperboard],
  ["Data", "/account", LineChart],
];

export function StudioNavigation() {
  return (
    <aside className="hidden h-[calc(100vh-86px)] border-r border-white/10 bg-ink/55 px-3 py-5 lg:block">
      <div className="flex h-full flex-col items-center justify-between">
        <div className="space-y-3">
          {navItems.map(([label, href, Icon], index) => (
            <Link
              key={String(label)}
              href={href}
              className={[
                "group grid size-12 place-items-center rounded-xl border transition",
                index === 0
                  ? "border-cyan/40 bg-cyan/15 text-cyan shadow-glow"
                  : "border-white/10 bg-white/[0.03] text-slate-500 hover:border-white/20 hover:bg-white/[0.07] hover:text-slate-200",
              ].join(" ")}
              title={String(label)}
            >
              <Icon size={19} />
            </Link>
          ))}
        </div>
        <div className="h-28 w-px bg-gradient-to-b from-transparent via-cyan/40 to-transparent" />
      </div>
    </aside>
  );
}
