create table if not exists public.avatar_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  video_url text not null default '',
  audio_url text not null default '',
  result_url text,
  status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed')),
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists avatar_tasks_user_id_created_at_idx
on public.avatar_tasks (user_id, created_at desc);

alter table public.avatar_tasks enable row level security;

drop policy if exists "Users can read own avatar tasks" on public.avatar_tasks;
create policy "Users can read own avatar tasks" on public.avatar_tasks
for select using (auth.uid() = user_id);

drop policy if exists "Users can insert own avatar tasks" on public.avatar_tasks;
create policy "Users can insert own avatar tasks" on public.avatar_tasks
for insert with check (auth.uid() = user_id);

drop policy if exists "Service role can manage avatar tasks" on public.avatar_tasks;
create policy "Service role can manage avatar tasks" on public.avatar_tasks
for all using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
