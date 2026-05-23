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
  product_highlights text not null default '',
  target_audience text not null default '',
  video_style text not null default '',
  use_digital_human boolean not null default true,
  production_mode text not null default 'semi_auto',
  selling_points jsonb not null default '[]'::jsonb,
  hook text not null default '',
  shot_list jsonb not null default '[]'::jsonb,
  title_options jsonb not null default '[]'::jsonb,
  caption text not null default '',
  cover_text text not null default '',
  cover_prompt text not null default '',
  hashtags jsonb not null default '[]'::jsonb,
  comment_prompt text not null default '',
  closing_cta text not null default '',
  admin_workflow jsonb not null default '[]'::jsonb,
  status text not null default 'pending' check (status in ('pending', 'scripting', 'producing', 'processing', 'completed', 'failed')),
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

alter table public.video_tasks
add column if not exists personal_image_url text;

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

alter table public.video_tasks
add column if not exists avatar_id text not null default 'sophia';

alter table public.video_tasks
add column if not exists voice_url text not null default '';

alter table public.video_tasks
add column if not exists tts_language text not null default 'zh';

alter table public.video_tasks
add column if not exists tts_voice_name text not null default 'minimax_zh_female';

alter table public.video_tasks
add column if not exists admin_notes text not null default '';

alter table public.video_tasks
add column if not exists subtitle_url text;

alter table public.video_tasks
add column if not exists subtitle_status text not null default 'pending';

alter table public.video_tasks
add column if not exists cloned_voice_url text;

alter table public.video_tasks
add column if not exists cosyvoice_status text not null default 'pending';

alter table public.video_tasks
add column if not exists heygen_avatar_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_voice_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_video_id text not null default '';

alter table public.video_tasks
add column if not exists heygen_video_url text not null default '';

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

create index if not exists video_tasks_user_email_idx on public.video_tasks (user_email);
create index if not exists video_tasks_created_at_idx on public.video_tasks (created_at desc);

alter table public.video_tasks enable row level security;

create policy "Service role can manage video tasks"
on public.video_tasks
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
