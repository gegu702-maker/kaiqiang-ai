-- Run this in Supabase SQL Editor if /debug/supabase reports that video_tasks is missing.
-- It mirrors the app schema needed for the AI digital human MVP.

create table if not exists public.video_tasks (
  id uuid primary key default gen_random_uuid(),
  user_email text not null,
  product_name text not null,
  script text not null,
  language text not null,
  image_url text not null,
  personal_image_url text,
  avatar_id text not null default 'sophia',
  voice_url text not null default '',
  tts_language text not null default 'zh',
  tts_voice_name text not null default 'minimax_zh_female',
  admin_notes text not null default '',
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
  result_video_url text,
  subtitle_url text,
  subtitle_status text not null default 'pending' check (subtitle_status in ('pending', 'completed', 'failed')),
  cloned_voice_url text,
  cosyvoice_status text not null default 'pending' check (cosyvoice_status in ('pending', 'generating', 'completed', 'failed')),
  heygen_avatar_id text not null default '',
  heygen_voice_id text not null default '',
  heygen_video_id text not null default '',
  heygen_video_url text not null default '',
  created_at timestamptz not null default now()
);

alter table public.video_tasks add column if not exists personal_image_url text;
alter table public.video_tasks add column if not exists avatar_id text not null default 'sophia';
alter table public.video_tasks add column if not exists voice_url text not null default '';
alter table public.video_tasks add column if not exists tts_language text not null default 'zh';
alter table public.video_tasks add column if not exists tts_voice_name text not null default 'minimax_zh_female';
alter table public.video_tasks add column if not exists admin_notes text not null default '';
alter table public.video_tasks add column if not exists subtitle_url text;
alter table public.video_tasks add column if not exists subtitle_status text not null default 'pending';
alter table public.video_tasks add column if not exists cloned_voice_url text;
alter table public.video_tasks add column if not exists cosyvoice_status text not null default 'pending';
alter table public.video_tasks add column if not exists heygen_avatar_id text not null default '';
alter table public.video_tasks add column if not exists heygen_voice_id text not null default '';
alter table public.video_tasks add column if not exists heygen_video_id text not null default '';
alter table public.video_tasks add column if not exists heygen_video_url text not null default '';

create index if not exists video_tasks_user_email_idx on public.video_tasks (user_email);
create index if not exists video_tasks_created_at_idx on public.video_tasks (created_at desc);

alter table public.video_tasks enable row level security;

drop policy if exists "Service role can manage video tasks" on public.video_tasks;
create policy "Service role can manage video tasks"
on public.video_tasks
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
