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

create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.profiles
    where id = auth.uid()
      and role = 'admin'
      and coalesce(status, 'active') <> 'banned'
  );
$$;

alter table public.profiles
drop constraint if exists profiles_plan_check;

alter table public.profiles
add column if not exists voice_clone_enabled boolean not null default false;

alter table public.profiles
add column if not exists default_voice_id text;

alter table public.profiles
add column if not exists credits integer not null default 3;

alter table public.profiles
add constraint profiles_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

update public.profiles
set plan = 'plus',
    monthly_quota = 100,
    voice_clone_enabled = false
where plan = 'pro'
  and coalesce(voice_clone_enabled, false) = false;

create table if not exists public.voice_clones (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  provider text not null default 'mock' check (provider in ('mock', 'elevenlabs', 'minimax', 'fishaudio', 'openvoice')),
  voice_id text not null default '',
  name text not null,
  sample_audio_url text not null,
  status text not null default 'uploaded' check (status in ('uploaded', 'pending', 'ready', 'completed', 'failed', 'deleted')),
  created_at timestamptz not null default now()
);

alter table public.video_tasks
add column if not exists voice_clone_id uuid references public.voice_clones(id) on delete set null;

alter table public.video_tasks
add column if not exists use_cloned_voice boolean not null default false;

alter table public.video_tasks
drop constraint if exists video_tasks_status_check;

alter table public.video_tasks
add constraint video_tasks_status_check
check (status in ('waiting', 'generating_script', 'cloning_voice', 'generating_voice', 'generating_avatar', 'rendering', 'success', 'pending', 'scripting', 'producing', 'processing', 'completed', 'failed'));

alter table public.task_queue
drop constraint if exists task_queue_status_check;

alter table public.task_queue
add constraint task_queue_status_check
check (status in ('waiting', 'generating_script', 'cloning_voice', 'generating_voice', 'generating_avatar', 'rendering', 'success', 'failed'));

alter table public.orders
drop constraint if exists orders_plan_check;

alter table public.orders
add constraint orders_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

alter table public.subscriptions
drop constraint if exists subscriptions_plan_check;

alter table public.subscriptions
add constraint subscriptions_plan_check
check (plan in ('free', 'plus', 'pro', 'business'));

create index if not exists voice_clones_user_created_idx on public.voice_clones (user_id, created_at desc);

alter table public.voice_clones enable row level security;

drop policy if exists "Users can read own voice clones" on public.voice_clones;
create policy "Users can read own voice clones" on public.voice_clones
for select using (auth.uid() = user_id);

drop policy if exists "Users can insert own voice clones" on public.voice_clones;
create policy "Users can insert own voice clones" on public.voice_clones
for insert with check (auth.uid() = user_id);

drop policy if exists "Users can update own voice clones" on public.voice_clones;
create policy "Users can update own voice clones" on public.voice_clones
for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users can delete own voice clones" on public.voice_clones;
create policy "Users can delete own voice clones" on public.voice_clones
for delete using (auth.uid() = user_id);

drop policy if exists "Admins can read all voice clones" on public.voice_clones;
create policy "Admins can read all voice clones" on public.voice_clones
for select using (public.is_admin());

drop policy if exists "Service role can manage voice clones" on public.voice_clones;
create policy "Service role can manage voice clones" on public.voice_clones
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
