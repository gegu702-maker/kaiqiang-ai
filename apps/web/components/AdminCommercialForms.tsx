"use client";

import { useActionState } from "react";

import { updateAdminPlanAction, updateAdminQuotaAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import type { AdminQuota, Plan } from "@/lib/types";

const initialState = { ok: false, message: "" };

export function AdminPlanForm({ plan }: { plan: Plan }) {
  const [state, action] = useActionState(updateAdminPlanAction, initialState);

  return (
    <form action={action} className="grid gap-3 lg:grid-cols-[100px_1fr_130px_130px_130px_110px_110px_auto]">
      <input type="hidden" name="code" value={plan.code} />
      <input
        name="name"
        defaultValue={plan.name}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="description"
        defaultValue={plan.description}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="monthly_quota"
        type="number"
        min={0}
        placeholder="无限"
        defaultValue={plan.monthly_quota ?? ""}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="monthly_price_cny"
        type="number"
        min={0}
        defaultValue={plan.monthly_price_cny}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="yearly_price_cny"
        type="number"
        min={0}
        defaultValue={plan.yearly_price_cny}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <select
        name="voice_clone_enabled"
        defaultValue={String(plan.voice_clone_enabled)}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-sm text-white"
      >
        <option value="true">clone on</option>
        <option value="false">clone off</option>
      </select>
      <select
        name="is_active"
        defaultValue={String(plan.is_active)}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-sm text-white"
      >
        <option value="true">active</option>
        <option value="false">hidden</option>
      </select>
      <SubmitButton label="保存" pendingLabel="保存中" />
      <label className="flex items-center gap-2 text-xs text-slate-400 lg:col-span-2">
        <input type="checkbox" name="monthly_quota_unlimited" value="true" defaultChecked={plan.monthly_quota === null} />
        月额度不限
      </label>
      <input type="hidden" name="sort_order" value={plan.sort_order} />
      {state.message ? <p className={state.ok ? "text-sm text-lime lg:col-span-8" : "text-sm text-rose-200 lg:col-span-8"}>{state.message}</p> : null}
    </form>
  );
}

export function AdminQuotaForm({ quota }: { quota: AdminQuota }) {
  const [state, action] = useActionState(updateAdminQuotaAction, initialState);

  return (
    <form action={action} className="grid gap-2 md:grid-cols-[1fr_110px_120px_120px_auto]">
      <input type="hidden" name="quota_id" value={quota.id} />
      <input
        readOnly
        value={quota.email || quota.user_id}
        className="h-10 rounded-md border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-300"
      />
      <input
        name="monthly_limit"
        type="number"
        min={0}
        defaultValue={quota.monthly_limit}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="used_count"
        type="number"
        min={0}
        defaultValue={quota.used_count}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <input
        name="remaining_count"
        type="number"
        min={0}
        defaultValue={quota.remaining_count}
        className="h-10 rounded-md border border-white/10 bg-ink/70 px-3 text-sm text-white"
      />
      <SubmitButton label="保存" pendingLabel="保存中" />
      {state.message ? <p className={state.ok ? "text-sm text-lime md:col-span-5" : "text-sm text-rose-200 md:col-span-5"}>{state.message}</p> : null}
    </form>
  );
}
