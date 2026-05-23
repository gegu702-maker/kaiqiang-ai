"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { motion } from "framer-motion";

import { Card } from "@/components/ui/card";
import { avatarProfiles } from "@/lib/avatars";
import { cn } from "@/lib/utils";

export function AvatarSelector() {
  const [selected, setSelected] = useState("sophia");

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-200">AI 主播选择</h3>
        <p className="mt-1 text-xs text-slate-500">固定数字人，不涉及训练、克隆或 GPU 推理。</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {avatarProfiles.map((avatar, index) => {
          const isSelected = selected === avatar.id;

          return (
            <motion.label
              key={avatar.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04, duration: 0.22 }}
              whileHover={{ y: -2 }}
              className="cursor-pointer"
            >
              <input
                required
                type="radio"
                name="avatar_id"
                value={avatar.id}
                checked={isSelected}
                onChange={() => setSelected(avatar.id)}
                className="sr-only"
              />
              <Card
                className={cn(
                  "relative flex items-center gap-3 p-3 transition",
                  isSelected ? "border-cyan/60 bg-cyan/10" : "hover:border-white/20 hover:bg-white/[0.06]",
                )}
              >
                <div className={cn("grid size-14 shrink-0 place-items-center rounded-lg bg-gradient-to-br", avatar.accent)}>
                  <span className="text-sm font-bold text-ink">{avatar.initials}</span>
                </div>
                <div className="min-w-0">
                  <p className="font-semibold text-white">{avatar.name}</p>
                  <p className="mt-1 inline-flex rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-slate-300">
                    {avatar.label}
                  </p>
                </div>
                {isSelected ? (
                  <motion.span
                    layoutId="avatar-check"
                    className="absolute right-3 top-3 grid size-6 place-items-center rounded-full bg-cyan text-ink"
                  >
                    <Check size={14} />
                  </motion.span>
                ) : null}
              </Card>
            </motion.label>
          );
        })}
      </div>
    </section>
  );
}
