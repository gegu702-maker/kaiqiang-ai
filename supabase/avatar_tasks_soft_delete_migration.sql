alter table public.avatar_tasks
add column if not exists deleted_at timestamptz;

create index if not exists avatar_tasks_user_id_deleted_at_created_at_idx
on public.avatar_tasks (user_id, deleted_at, created_at desc);
