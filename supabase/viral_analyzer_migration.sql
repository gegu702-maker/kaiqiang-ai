-- Viral Script Analyzer MVP.
-- Stores user analysis history and reserves usage_logs action="viral_analyze" for future quota reporting.

create table if not exists public.viral_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_url text not null default '',
  raw_script text not null default '',
  industry text not null,
  language text not null default 'zh',
  topic text not null default '',
  hook text not null default '',
  selling_points jsonb not null default '[]'::jsonb,
  structure jsonb not null default '[]'::jsonb,
  template_text text not null default '',
  rewrites jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint viral_analyses_industry_check check (industry in ('ecommerce', 'knowledge', 'training', 'local', 'personal_brand', 'global')),
  constraint viral_analyses_language_check check (language in ('zh', 'en'))
);

create index if not exists viral_analyses_user_created_idx
on public.viral_analyses (user_id, created_at desc);

alter table public.viral_analyses enable row level security;

drop policy if exists "Users can read own viral analyses" on public.viral_analyses;
create policy "Users can read own viral analyses" on public.viral_analyses
for select using (auth.uid() = user_id);

drop policy if exists "Service role can manage viral analyses" on public.viral_analyses;
create policy "Service role can manage viral analyses" on public.viral_analyses
for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
