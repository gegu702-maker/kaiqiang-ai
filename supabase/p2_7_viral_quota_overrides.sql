-- P2.7 Viral Analyzer temporary quota overrides.
-- Scope: Viral Analyzer only. Does not affect profiles.plan or user_quotas.

create table if not exists public.viral_quota_overrides (
  user_id uuid primary key references auth.users(id) on delete cascade,
  extra_monthly_limit integer not null default 0,
  expires_at timestamptz null,
  reason text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint viral_quota_overrides_extra_monthly_limit_check
    check (extra_monthly_limit >= 0)
);

create index if not exists viral_quota_overrides_user_id_idx
on public.viral_quota_overrides (user_id);

create index if not exists viral_quota_overrides_expires_at_idx
on public.viral_quota_overrides (expires_at);

alter table public.viral_quota_overrides enable row level security;

drop policy if exists "Service role can manage viral quota overrides"
on public.viral_quota_overrides;

create policy "Service role can manage viral quota overrides"
on public.viral_quota_overrides
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
