-- Avatar SaaS user validation: free credits, usage logs, and payment provider placeholders.

alter table public.profiles
add column if not exists plan text not null default 'free';

alter table public.profiles
add column if not exists monthly_quota integer default 3;

alter table public.profiles
add column if not exists custom_quota integer;

alter table public.profiles
add column if not exists credits integer not null default 3;

alter table public.profiles
add column if not exists voice_clone_enabled boolean not null default false;

alter table public.profiles
drop constraint if exists profiles_plan_check;

alter table public.profiles
add constraint profiles_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

create table if not exists public.usage_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid,
  action text not null default 'generate_video',
  quantity integer not null default 1,
  period_start timestamptz not null default date_trunc('month', now()),
  created_at timestamptz not null default now()
);

create index if not exists usage_logs_user_period_idx
on public.usage_logs (user_id, period_start, created_at desc);

create table if not exists public.user_quotas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'free' check (plan in ('free', 'plus', 'pro', 'business')),
  monthly_limit integer not null default 3,
  used_count integer not null default 0,
  remaining_count integer not null default 3,
  reset_month text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, reset_month)
);

alter table public.orders
drop constraint if exists orders_provider_check;

alter table public.orders
add constraint orders_provider_check
check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'lemon_squeezy', 'creem', 'manual'));

alter table public.subscriptions
drop constraint if exists subscriptions_provider_check;

alter table public.subscriptions
add constraint subscriptions_provider_check
check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'lemon_squeezy', 'creem', 'manual'));

update public.profiles
set plan = coalesce(plan, 'free'),
    monthly_quota = coalesce(monthly_quota, 3),
    credits = greatest(coalesce(credits, 3), 0),
    voice_clone_enabled = coalesce(voice_clone_enabled, false),
    updated_at = now();

notify pgrst, 'reload schema';
