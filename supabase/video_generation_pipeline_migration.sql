alter table public.video_tasks
drop constraint if exists video_tasks_status_check;

alter table public.video_tasks
add constraint video_tasks_status_check
check (status in ('waiting', 'processing', 'completed', 'failed', 'generating_script', 'cloning_voice', 'generating_voice', 'generating_avatar', 'rendering', 'success', 'pending', 'scripting', 'producing'));

alter table public.task_queue
drop constraint if exists task_queue_status_check;

alter table public.task_queue
add constraint task_queue_status_check
check (status in ('waiting', 'processing', 'generating_script', 'cloning_voice', 'generating_voice', 'generating_avatar', 'rendering', 'completed', 'success', 'failed'));

notify pgrst, 'reload schema';
