begin;

alter table public.video_tasks
add column if not exists generation_error text not null default '';

create table if not exists public.task_logs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.video_tasks(id) on delete cascade,
  level text not null default 'info' check (level in ('debug', 'info', 'warning', 'error')),
  message text not null default '',
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists task_logs_task_created_idx
on public.task_logs (task_id, created_at desc);

alter table public.task_logs enable row level security;

drop policy if exists "Users can read own task logs" on public.task_logs;

create policy "Users can read own task logs"
on public.task_logs
for select
using (
  exists (
    select 1
    from public.video_tasks
    where video_tasks.id = task_logs.task_id
      and video_tasks.user_id = auth.uid()
  )
);

drop policy if exists "Service role can manage task logs" on public.task_logs;

create policy "Service role can manage task logs"
on public.task_logs
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';

commit;
