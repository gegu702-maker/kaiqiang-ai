alter table public.video_tasks
add column if not exists product_highlights text not null default '';

alter table public.video_tasks
add column if not exists target_audience text not null default '';

alter table public.video_tasks
add column if not exists video_style text not null default '';

alter table public.video_tasks
add column if not exists use_digital_human boolean not null default true;

alter table public.video_tasks
add column if not exists production_mode text not null default 'semi_auto';

alter table public.video_tasks
add column if not exists selling_points jsonb not null default '[]'::jsonb;

alter table public.video_tasks
add column if not exists hook text not null default '';

alter table public.video_tasks
add column if not exists shot_list jsonb not null default '[]'::jsonb;

alter table public.video_tasks
add column if not exists title_options jsonb not null default '[]'::jsonb;

alter table public.video_tasks
add column if not exists caption text not null default '';

alter table public.video_tasks
add column if not exists cover_text text not null default '';

alter table public.video_tasks
add column if not exists cover_prompt text not null default '';

alter table public.video_tasks
add column if not exists hashtags jsonb not null default '[]'::jsonb;

alter table public.video_tasks
add column if not exists comment_prompt text not null default '';

alter table public.video_tasks
add column if not exists closing_cta text not null default '';

alter table public.video_tasks
add column if not exists admin_workflow jsonb not null default '[]'::jsonb;

alter table public.video_tasks
drop constraint if exists video_tasks_status_check;

alter table public.video_tasks
add constraint video_tasks_status_check
check (status in ('pending', 'scripting', 'producing', 'processing', 'completed', 'failed'));

notify pgrst, 'reload schema';
