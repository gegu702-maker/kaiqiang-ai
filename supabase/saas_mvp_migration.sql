create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  plan text not null default 'free' check (plan in ('free', 'pro', 'business')),
  monthly_quota integer not null default 3,
  custom_quota integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.billing_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  billing_name text not null default '',
  billing_email text not null default '',
  country text not null default 'CN',
  currency text not null default 'CNY',
  tax_id text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'free' check (plan in ('free', 'pro', 'business')),
  status text not null default 'active' check (status in ('active', 'trialing', 'past_due', 'canceled')),
  provider text not null default 'manual' check (provider in ('wechat', 'alipay', 'stripe', 'paypal', 'manual')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null check (plan in ('free', 'pro', 'business')),
  currency text not null default 'CNY',
  amount integer not null default 0,
  provider text not null default 'manual' check (provider in ('wechat', 'alipay', 'stripe', 'paypal', 'manual')),
  status text not null default 'pending' check (status in ('pending', 'paid', 'failed', 'refunded')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid references public.orders(id) on delete set null,
  user_id uuid not null references auth.users(id) on delete cascade,
  provider text not null check (provider in ('wechat', 'alipay', 'stripe', 'paypal', 'manual')),
  status text not null default 'pending' check (status in ('pending', 'paid', 'failed', 'refunded')),
  provider_payment_id text not null default '',
  amount integer not null default 0,
  currency text not null default 'CNY',
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.usage_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid references public.video_tasks(id) on delete set null,
  action text not null default 'generate_video',
  quantity integer not null default 1,
  period_start timestamptz not null,
  created_at timestamptz not null default now()
);

alter table public.video_tasks
add column if not exists user_id uuid references auth.users(id) on delete set null;

create index if not exists video_tasks_user_id_idx on public.video_tasks (user_id);
create index if not exists usage_logs_user_period_idx on public.usage_logs (user_id, period_start);
create index if not exists orders_user_created_idx on public.orders (user_id, created_at desc);
create index if not exists subscriptions_user_status_idx on public.subscriptions (user_id, status);

alter table public.profiles enable row level security;
alter table public.billing_profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.orders enable row level security;
alter table public.payments enable row level security;
alter table public.usage_logs enable row level security;
alter table public.video_tasks enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile" on public.profiles
for select using (auth.uid() = id);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile" on public.profiles
for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "Users can read own billing profiles" on public.billing_profiles;
create policy "Users can read own billing profiles" on public.billing_profiles
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own subscriptions" on public.subscriptions;
create policy "Users can read own subscriptions" on public.subscriptions
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own orders" on public.orders;
create policy "Users can read own orders" on public.orders
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own payments" on public.payments;
create policy "Users can read own payments" on public.payments
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own usage logs" on public.usage_logs;
create policy "Users can read own usage logs" on public.usage_logs
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own video tasks" on public.video_tasks;
create policy "Users can read own video tasks" on public.video_tasks
for select using (auth.uid() = user_id);

drop policy if exists "Users can insert own video tasks" on public.video_tasks;
create policy "Users can insert own video tasks" on public.video_tasks
for insert with check (auth.uid() = user_id);

drop policy if exists "Service role can manage profiles" on public.profiles;
create policy "Service role can manage profiles" on public.profiles
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage billing profiles" on public.billing_profiles;
create policy "Service role can manage billing profiles" on public.billing_profiles
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage subscriptions" on public.subscriptions;
create policy "Service role can manage subscriptions" on public.subscriptions
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage orders" on public.orders;
create policy "Service role can manage orders" on public.orders
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage payments" on public.payments;
create policy "Service role can manage payments" on public.payments
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage usage logs" on public.usage_logs;
create policy "Service role can manage usage logs" on public.usage_logs
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
