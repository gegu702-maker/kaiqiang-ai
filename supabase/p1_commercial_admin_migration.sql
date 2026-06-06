-- P1 commercial admin schema.
-- Scope: plans, subscriptions, payments, orders, and quota admin support only.

create table if not exists public.plans (
  code text primary key,
  name text not null,
  description text not null default '',
  monthly_quota integer,
  monthly_price_cny integer not null default 0,
  yearly_price_cny integer not null default 0,
  voice_clone_enabled boolean not null default false,
  is_active boolean not null default true,
  sort_order integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint plans_code_check check (code in ('free', 'plus', 'pro', 'business')),
  constraint plans_monthly_quota_check check (monthly_quota is null or monthly_quota >= 0),
  constraint plans_price_check check (monthly_price_cny >= 0 and yearly_price_cny >= 0)
);

insert into public.plans (
  code,
  name,
  description,
  monthly_quota,
  monthly_price_cny,
  yearly_price_cny,
  voice_clone_enabled,
  is_active,
  sort_order
)
values
  ('free', 'Free', '免费体验额度', 3, 0, 0, false, true, 10),
  ('plus', 'Plus', '轻量创作者套餐', 100, 19900, 199000, false, true, 20),
  ('pro', 'Pro', '专业创作者套餐', 1000, 79900, 799000, true, true, 30),
  ('business', 'Business', '企业定制套餐', null, 0, 0, true, true, 40)
on conflict (code) do update
set name = excluded.name,
    description = excluded.description,
    monthly_quota = excluded.monthly_quota,
    monthly_price_cny = excluded.monthly_price_cny,
    yearly_price_cny = excluded.yearly_price_cny,
    voice_clone_enabled = excluded.voice_clone_enabled,
    is_active = excluded.is_active,
    sort_order = excluded.sort_order,
    updated_at = now();

alter table public.profiles
add column if not exists role text not null default 'user';

alter table public.profiles
add column if not exists status text not null default 'active';

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

alter table public.subscriptions
add column if not exists cancel_at_period_end boolean not null default false;

alter table public.subscriptions
add column if not exists provider_subscription_id text not null default '';

alter table public.subscriptions
drop constraint if exists subscriptions_plan_check;

alter table public.subscriptions
add constraint subscriptions_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

alter table public.subscriptions
drop constraint if exists subscriptions_provider_check;

alter table public.subscriptions
add constraint subscriptions_provider_check
check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'lemon_squeezy', 'creem', 'manual'));

alter table public.orders
add column if not exists billing_cycle text not null default 'monthly';

alter table public.orders
drop constraint if exists orders_plan_check;

alter table public.orders
add constraint orders_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

alter table public.orders
drop constraint if exists orders_billing_cycle_check;

alter table public.orders
add constraint orders_billing_cycle_check
check (billing_cycle in ('monthly', 'yearly'));

alter table public.orders
drop constraint if exists orders_provider_check;

alter table public.orders
add constraint orders_provider_check
check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'lemon_squeezy', 'creem', 'manual'));

alter table public.payments
drop constraint if exists payments_provider_check;

alter table public.payments
add constraint payments_provider_check
check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'lemon_squeezy', 'creem', 'manual'));

alter table public.user_quotas
drop constraint if exists user_quotas_plan_check;

alter table public.user_quotas
add constraint user_quotas_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

create index if not exists plans_active_sort_idx on public.plans (is_active, sort_order);
create index if not exists payments_user_created_idx on public.payments (user_id, created_at desc);
create index if not exists subscriptions_user_created_idx on public.subscriptions (user_id, created_at desc);
create index if not exists user_quotas_reset_month_idx on public.user_quotas (reset_month, updated_at desc);

alter table public.plans enable row level security;

drop policy if exists "Anyone can read active plans" on public.plans;
create policy "Anyone can read active plans" on public.plans
for select using (is_active = true);

drop policy if exists "Service role can manage plans" on public.plans;
create policy "Service role can manage plans" on public.plans
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
