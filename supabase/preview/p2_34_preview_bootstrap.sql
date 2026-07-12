-- PREVIEW-ONLY BOOTSTRAP
-- DO NOT RUN AGAINST PRODUCTION
-- Target project: kaiqiang-p2-34-preview
-- This script is intended only for a new, isolated Supabase Preview project.
-- It must not copy or reference Production data, users, storage, secrets, or project refs.
-- This is an empty-project bootstrap, not an upgrade or reconciliation migration.
-- Re-running it is intended only for audit/bootstrap recovery in the same isolated Preview project.
-- create table if not exists does not repair an existing table with missing or incompatible columns.
--
-- VALIDATION STATUS:
-- PostgreSQL grammar has been parser-validated with pglast 8.2.
-- Empty-database execution has not yet been validated.
-- Runtime idempotency has not yet been validated.
-- Supabase Auth, RLS, Storage, and runtime behavior have not yet been validated.
--
-- REQUIRED MANUAL SAFETY CHECKS BEFORE EXECUTION:
-- 1. Record the Preview Supabase project ref.
-- 2. Record the Production Supabase project ref.
-- 3. Confirm the two project refs are different.
-- 4. Confirm the SQL Editor browser tab belongs to the Preview project.
-- 5. Close any Production SQL Editor tab before running this script.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  plan text not null default 'free',
  monthly_quota integer not null default 3,
  custom_quota integer,
  credits integer not null default 3,
  voice_clone_enabled boolean not null default false,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_plan_check check (plan in ('free', 'plus', 'pro', 'business')),
  constraint profiles_status_check check (status in ('active', 'banned')),
  constraint profiles_monthly_quota_check check (monthly_quota >= 0),
  constraint profiles_custom_quota_check check (custom_quota is null or custom_quota >= 0),
  constraint profiles_credits_check check (credits >= 0)
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'free',
  status text not null default 'active',
  provider text not null default 'manual',
  current_period_start timestamptz,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint subscriptions_plan_check check (plan in ('free', 'plus', 'pro', 'business')),
  constraint subscriptions_status_check check (status in ('active', 'trialing', 'past_due', 'canceled')),
  constraint subscriptions_provider_check check (provider = 'manual')
);

create unique index if not exists subscriptions_one_active_per_user_idx
on public.subscriptions (user_id)
where status = 'active';

create index if not exists subscriptions_user_created_at_idx
on public.subscriptions (user_id, created_at desc);

create table if not exists public.user_quotas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'free',
  monthly_limit integer not null default 3,
  used_count integer not null default 0,
  remaining_count integer not null default 3,
  reset_month text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_quotas_plan_check check (plan in ('free', 'plus', 'pro', 'business')),
  constraint user_quotas_monthly_limit_check check (monthly_limit >= 0),
  constraint user_quotas_used_count_check check (used_count >= 0),
  constraint user_quotas_remaining_count_check check (remaining_count >= 0),
  constraint user_quotas_reset_month_check check (reset_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  constraint user_quotas_user_month_key unique (user_id, reset_month)
);

create index if not exists user_quotas_user_month_idx
on public.user_quotas (user_id, reset_month);

create table if not exists public.avatar_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  video_url text not null default '',
  audio_url text not null default '',
  result_url text,
  status text not null default 'queued',
  progress_stage text not null default 'queued',
  error_message text,
  last_gpu_used_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint avatar_tasks_status_check check (status in ('queued', 'running', 'completed', 'failed')),
  constraint avatar_tasks_progress_stage_check check (
    progress_stage in ('queued', 'gpu_starting', 'model_loading', 'video_generating', 'completed', 'failed')
  )
);

create index if not exists avatar_tasks_user_id_created_at_idx
on public.avatar_tasks (user_id, created_at desc);

create index if not exists avatar_tasks_user_id_deleted_at_created_at_idx
on public.avatar_tasks (user_id, deleted_at, created_at desc);

create table if not exists public.usage_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid,
  avatar_task_id uuid references public.avatar_tasks(id) on delete set null,
  action text not null default 'generate_video',
  quantity integer not null default 1,
  period_start timestamptz not null default date_trunc('month', now()),
  created_at timestamptz not null default now(),
  constraint usage_logs_quantity_check check (quantity >= 0)
);

create index if not exists usage_logs_user_period_created_at_idx
on public.usage_logs (user_id, period_start, created_at desc);

create index if not exists usage_logs_avatar_task_id_idx
on public.usage_logs (avatar_task_id);

-- No uniqueness constraint is placed on avatar_task_id or (avatar_task_id, action).
-- Current API compatibility fallback retries a failed usage insert without task linkage,
-- so a uniqueness constraint alone would not provide reliable end-to-end deduplication.

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists subscriptions_set_updated_at on public.subscriptions;
create trigger subscriptions_set_updated_at
before update on public.subscriptions
for each row execute function public.set_updated_at();

drop trigger if exists user_quotas_set_updated_at on public.user_quotas;
create trigger user_quotas_set_updated_at
before update on public.user_quotas
for each row execute function public.set_updated_at();

drop trigger if exists avatar_tasks_set_updated_at on public.avatar_tasks;
create trigger avatar_tasks_set_updated_at
before update on public.avatar_tasks
for each row execute function public.set_updated_at();

create or replace function public.initialize_preview_free_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  month_key text := to_char(now(), 'YYYY-MM');
  period_start timestamptz := date_trunc('month', now());
begin
  insert into public.profiles (
    id,
    email,
    plan,
    monthly_quota,
    custom_quota,
    credits,
    voice_clone_enabled,
    status
  )
  values (
    new.id,
    coalesce(new.email, ''),
    'free',
    3,
    null,
    3,
    false,
    'active'
  )
  on conflict (id) do nothing;

  insert into public.subscriptions (
    user_id,
    plan,
    status,
    provider,
    current_period_start,
    current_period_end
  )
  select
    new.id,
    'free',
    'active',
    'manual',
    period_start,
    period_start + interval '1 month'
  where not exists (
    select 1
    from public.subscriptions
    where user_id = new.id
      and status = 'active'
  );

  insert into public.user_quotas (
    user_id,
    plan,
    monthly_limit,
    used_count,
    remaining_count,
    reset_month
  )
  values (
    new.id,
    'free',
    3,
    0,
    3,
    month_key
  )
  on conflict (user_id, reset_month) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created_initialize_preview_free_user on auth.users;
create trigger on_auth_user_created_initialize_preview_free_user
after insert on auth.users
for each row execute function public.initialize_preview_free_user();

alter table public.profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.user_quotas enable row level security;
alter table public.usage_logs enable row level security;
alter table public.avatar_tasks enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile" on public.profiles
for select to authenticated
using (auth.uid() = id);

drop policy if exists "Users can read own subscriptions" on public.subscriptions;
create policy "Users can read own subscriptions" on public.subscriptions
for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can read own quotas" on public.user_quotas;
create policy "Users can read own quotas" on public.user_quotas
for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can read own usage logs" on public.usage_logs;
create policy "Users can read own usage logs" on public.usage_logs
for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can read own avatar tasks" on public.avatar_tasks;
create policy "Users can read own avatar tasks" on public.avatar_tasks
for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert own avatar tasks" on public.avatar_tasks;
create policy "Users can insert own avatar tasks" on public.avatar_tasks
for insert to authenticated
with check (auth.uid() = user_id);

-- The plans table is intentionally omitted. Current API code falls back to built-in
-- plan metadata when the table is absent; no Production pricing is copied here.

-- Level 1 intentionally creates no Storage bucket.
-- Before Level 2, manually create an isolated Preview bucket named "voices".

-- OPTIONAL MANUAL SEED TEMPLATE (COMMENTED OUT; DO NOT RUN UNCHANGED)
-- Replace <PREVIEW_AUTH_USER_UUID> only after creating the Preview-only Auth user.
-- Do not use a Production user UUID.
-- The auth trigger normally creates these rows; this template is only for explicit recovery/audit.
--
-- insert into public.profiles (
--   id, email, plan, monthly_quota, custom_quota, credits, voice_clone_enabled, status
-- ) values (
--   '<PREVIEW_AUTH_USER_UUID>'::uuid, '', 'free', 3, null, 3, false, 'active'
-- ) on conflict (id) do nothing;
--
-- insert into public.subscriptions (
--   user_id, plan, status, provider, current_period_start, current_period_end
-- )
-- select
--   '<PREVIEW_AUTH_USER_UUID>'::uuid,
--   'free',
--   'active',
--   'manual',
--   date_trunc('month', now()),
--   date_trunc('month', now()) + interval '1 month'
-- where not exists (
--   select 1 from public.subscriptions
--   where user_id = '<PREVIEW_AUTH_USER_UUID>'::uuid and status = 'active'
-- );
--
-- insert into public.user_quotas (
--   user_id, plan, monthly_limit, used_count, remaining_count, reset_month
-- ) values (
--   '<PREVIEW_AUTH_USER_UUID>'::uuid, 'free', 3, 0, 3, to_char(now(), 'YYYY-MM')
-- ) on conflict (user_id, reset_month) do nothing;

notify pgrst, 'reload schema';
