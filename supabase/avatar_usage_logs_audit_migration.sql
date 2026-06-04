-- Avatar usage audit linkage. Keeps legacy usage_logs.task_id for video_tasks.

alter table public.usage_logs
add column if not exists avatar_task_id uuid references public.avatar_tasks(id) on delete set null;

create index if not exists usage_logs_avatar_task_id_idx
on public.usage_logs (avatar_task_id);

notify pgrst, 'reload schema';
