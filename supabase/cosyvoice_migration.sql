alter table public.video_tasks
add column if not exists cloned_voice_url text;

alter table public.video_tasks
add column if not exists cosyvoice_status text not null default 'pending';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'video_tasks_cosyvoice_status_check'
  ) then
    alter table public.video_tasks
    add constraint video_tasks_cosyvoice_status_check
    check (cosyvoice_status in ('pending', 'generating', 'completed', 'failed'));
  end if;
end $$;

notify pgrst, 'reload schema';
