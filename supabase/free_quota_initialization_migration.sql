-- Fix Free quota initialization for new and existing users.
-- Run this in Supabase SQL Editor after the SaaS MVP migrations.

alter table public.profiles
add column if not exists role text not null default 'user';

alter table public.profiles
add column if not exists status text not null default 'active';

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
add column if not exists default_voice_id text;

alter table public.profiles
drop constraint if exists profiles_plan_check;

alter table public.profiles
add constraint profiles_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

alter table public.profiles
drop constraint if exists profiles_status_check;

alter table public.profiles
add constraint profiles_status_check
check (status in ('active', 'banned'));

update public.profiles
set plan = coalesce(plan, 'free'),
    monthly_quota = coalesce(monthly_quota, 3),
    credits = greatest(coalesce(credits, 3), 3),
    status = coalesce(status, 'active'),
    voice_clone_enabled = coalesce(voice_clone_enabled, false),
    updated_at = now()
where plan is null
   or monthly_quota is null
   or credits is null
   or status is null
   or voice_clone_enabled is null;

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

create index if not exists user_quotas_user_month_idx
on public.user_quotas (user_id, reset_month);

alter table public.user_quotas enable row level security;

drop policy if exists "Users can read own quotas" on public.user_quotas;
create policy "Users can read own quotas" on public.user_quotas
for select using (auth.uid() = user_id);

drop policy if exists "Service role can manage quotas" on public.user_quotas;
create policy "Service role can manage quotas" on public.user_quotas
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

insert into public.profiles (
  id,
  email,
  plan,
  monthly_quota,
  credits,
  status,
  voice_clone_enabled
)
select
  users.id,
  coalesce(users.email, ''),
  'free',
  3,
  3,
  'active',
  false
from auth.users
left join public.profiles on profiles.id = users.id
where profiles.id is null
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
  profiles.id,
  coalesce(profiles.plan, 'free'),
  'active',
  'manual',
  date_trunc('month', now()),
  date_trunc('month', now()) + interval '1 month'
from public.profiles
where not exists (
  select 1
  from public.subscriptions
  where subscriptions.user_id = profiles.id
    and subscriptions.status = 'active'
)
on conflict do nothing;

insert into public.user_quotas (
  user_id,
  plan,
  monthly_limit,
  used_count,
  remaining_count,
  reset_month
)
select
  profiles.id,
  coalesce(profiles.plan, 'free'),
  coalesce(profiles.custom_quota, profiles.monthly_quota, 3),
  0,
  coalesce(profiles.custom_quota, profiles.monthly_quota, 3),
  to_char(now(), 'YYYY-MM')
from public.profiles
where not exists (
  select 1
  from public.user_quotas
  where user_quotas.user_id = profiles.id
    and user_quotas.reset_month = to_char(now(), 'YYYY-MM')
)
on conflict (user_id, reset_month) do nothing;

create or replace function public.initialize_free_user_defaults()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  month_key text := to_char(now(), 'YYYY-MM');
begin
  insert into public.profiles (
    id,
    email,
    plan,
    monthly_quota,
    credits,
    status,
    voice_clone_enabled
  )
  values (
    new.id,
    coalesce(new.email, ''),
    'free',
    3,
    3,
    'active',
    false
  )
  on conflict (id) do update
  set email = excluded.email,
      plan = coalesce(public.profiles.plan, 'free'),
      monthly_quota = coalesce(public.profiles.monthly_quota, 3),
      credits = greatest(coalesce(public.profiles.credits, 3), 3),
      status = coalesce(public.profiles.status, 'active'),
      voice_clone_enabled = coalesce(public.profiles.voice_clone_enabled, false),
      updated_at = now();

  insert into public.subscriptions (
    user_id,
    plan,
    status,
    provider,
    current_period_start,
    current_period_end
  )
  values (
    new.id,
    'free',
    'active',
    'manual',
    date_trunc('month', now()),
    date_trunc('month', now()) + interval '1 month'
  )
  on conflict do nothing;

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

drop trigger if exists on_auth_user_created_initialize_free_quota on auth.users;

create trigger on_auth_user_created_initialize_free_quota
after insert on auth.users
for each row execute function public.initialize_free_user_defaults();

notify pgrst, 'reload schema';
