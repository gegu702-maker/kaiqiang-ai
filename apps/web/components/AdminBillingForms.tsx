"use client";

import { useActionState } from "react";

import { markOrderPaidAction, updateAdminUserAction } from "@/app/actions/admin";
import { SubmitButton } from "@/components/SubmitButton";
import type { AdminUser, Order } from "@/lib/types";

const initialState = { ok: false, message: "" };

export function AdminUserForm({ user }: { user: AdminUser }) {
  const [state, action] = useActionState(updateAdminUserAction, initialState);

  return (
    <form action={action} className="grid gap-2 md:grid-cols-[1fr_120px_120px_120px_auto]">
      <input type="hidden" name="user_id" value={user.id} />
      <input readOnly value={user.email} className="h-10 rounded-md border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-300" />
      <select name="plan" defaultValue={user.plan} className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-sm">
        <option value="free">free</option>
        <option value="pro">pro</option>
        <option value="business">business</option>
      </select>
      <input name="custom_quota" type="number" min={0} placeholder="自定义额度" defaultValue={user.custom_quota ?? ""} className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-sm" />
      <select name="status" defaultValue={user.status ?? "active"} className="h-10 rounded-md border border-white/10 bg-ink/70 px-2 text-sm">
        <option value="active">active</option>
        <option value="banned">banned</option>
      </select>
      <SubmitButton label="保存" pendingLabel="保存中" />
      {state.message ? <p className={state.ok ? "text-sm text-lime md:col-span-5" : "text-sm text-rose-200 md:col-span-5"}>{state.message}</p> : null}
    </form>
  );
}

export function AdminOrderPaidForm({ order }: { order: Order }) {
  const [state, action] = useActionState(markOrderPaidAction, initialState);

  return (
    <form action={action} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="order_id" value={order.id} />
      <input name="provider_payment_id" placeholder="payment id" className="h-9 rounded-md border border-white/10 bg-ink/70 px-2 text-xs" />
      <SubmitButton label="标记已支付" pendingLabel="处理中" />
      {state.message ? <span className={state.ok ? "text-xs text-lime" : "text-xs text-rose-200"}>{state.message}</span> : null}
    </form>
  );
}
