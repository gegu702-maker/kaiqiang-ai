alter table public.video_tasks
add column if not exists personal_image_url text;

alter table public.video_tasks
add column if not exists heygen_avatar_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_voice_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_video_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_video_url text not null default '';

notify pgrst, 'reload schema';
