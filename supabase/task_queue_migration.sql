begin;

create table if not exists public.task_queue (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.video_tasks(id) on delete cascade,
  user_id uuid references auth.users(id) on delete set null,
  status text not null default 'waiting',
  payload jsonb not null default '{}'::jsonb,
  attempts integer not null default 0,
  error_message text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.task_queue
drop constraint if exists task_queue_status_check;

alter table public.task_queue
add constraint task_queue_status_check
check (
  status in (
    'pending',
    'waiting',
    'queued',
    'processing',
    'generating_script',
    'cloning_voice',
    'generating_voice',
    'generating_avatar',
    'rendering',
    'completed',
    'success',
    'failed'
  )
);

create index if not exists task_queue_status_created_idx
on public.task_queue (status, created_at);

create index if not exists task_queue_task_id_idx
on public.task_queue (task_id);

create or replace function public.set_task_queue_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_task_queue_updated_at on public.task_queue;

create trigger set_task_queue_updated_at
before update on public.task_queue
for each row
execute function public.set_task_queue_updated_at();

alter table public.task_queue enable row level security;

drop policy if exists "Users can read own task queue" on public.task_queue;

create policy "Users can read own task queue"
on public.task_queue
for select
using (auth.uid() = user_id);

drop policy if exists "Service role can manage task queue" on public.task_queue;

create policy "Service role can manage task queue"
on public.task_queue
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';

commit;

-- 验证 task_queue 是否创建成功
select
  table_schema,
  table_name
from information_schema.tables
where table_schema = 'public'
  and table_name = 'task_queue';

-- 验证 task_queue status 约束
select
  conname,
  pg_get_constraintdef(oid) as constraint_definition
from pg_constraint
where conrelid = 'public.task_queue'::regclass
  and conname = 'task_queue_status_check';
