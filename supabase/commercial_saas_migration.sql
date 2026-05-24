alter table public.profiles
add column if not exists status text not null default 'active';

alter table public.profiles
drop constraint if exists profiles_status_check;

alter table public.profiles
add constraint profiles_status_check check (status in ('active', 'banned'));

alter table public.orders
add column if not exists billing_cycle text not null default 'monthly';

alter table public.orders
drop constraint if exists orders_provider_check;

alter table public.orders
add constraint orders_provider_check check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'manual'));

alter table public.payments
drop constraint if exists payments_provider_check;

alter table public.payments
add constraint payments_provider_check check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'manual'));

alter table public.subscriptions
drop constraint if exists subscriptions_provider_check;

alter table public.subscriptions
add constraint subscriptions_provider_check check (provider in ('wechat', 'alipay', 'pingpp', 'stripe', 'paypal', 'manual'));

alter table public.orders
drop constraint if exists orders_billing_cycle_check;

alter table public.orders
add constraint orders_billing_cycle_check check (billing_cycle in ('monthly', 'yearly'));

alter table public.video_tasks
drop constraint if exists video_tasks_status_check;

alter table public.video_tasks
add constraint video_tasks_status_check
check (status in ('waiting', 'generating_script', 'generating_voice', 'generating_avatar', 'rendering', 'success', 'pending', 'scripting', 'producing', 'processing', 'completed', 'failed'));

alter table public.video_tasks
add column if not exists voice_duration numeric;

alter table public.video_tasks
add column if not exists talking_video_url text;

alter table public.video_tasks
add column if not exists generation_error text not null default '';

create table if not exists public.api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null default 'Default API Key',
  key_prefix text not null,
  key_hash text not null,
  status text not null default 'active' check (status in ('active', 'revoked')),
  last_used_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.task_queue (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.video_tasks(id) on delete cascade,
  user_id uuid references auth.users(id) on delete set null,
  status text not null default 'waiting' check (status in ('waiting', 'generating_script', 'generating_voice', 'generating_avatar', 'rendering', 'success', 'failed')),
  attempts integer not null default 0,
  error_message text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.task_logs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.video_tasks(id) on delete cascade,
  level text not null default 'info' check (level in ('info', 'warning', 'error')),
  message text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists api_keys_user_id_idx on public.api_keys (user_id);
create index if not exists task_queue_status_created_idx on public.task_queue (status, created_at);
create index if not exists task_logs_task_created_idx on public.task_logs (task_id, created_at desc);

alter table public.api_keys enable row level security;
alter table public.task_queue enable row level security;
alter table public.task_logs enable row level security;

drop policy if exists "Users can read own api keys" on public.api_keys;
create policy "Users can read own api keys" on public.api_keys
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own task queue" on public.task_queue;
create policy "Users can read own task queue" on public.task_queue
for select using (auth.uid() = user_id);

drop policy if exists "Users can read own task logs" on public.task_logs;
create policy "Users can read own task logs" on public.task_logs
for select using (
  exists (
    select 1 from public.video_tasks
    where video_tasks.id = task_logs.task_id
    and video_tasks.user_id = auth.uid()
  )
);

drop policy if exists "Service role can manage api keys" on public.api_keys;
create policy "Service role can manage api keys" on public.api_keys
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage task queue" on public.task_queue;
create policy "Service role can manage task queue" on public.task_queue
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

drop policy if exists "Service role can manage task logs" on public.task_logs;
create policy "Service role can manage task logs" on public.task_logs
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
