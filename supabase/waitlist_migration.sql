create table if not exists public.waitlist (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  industry text not null default '',
  use_case text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists waitlist_created_at_idx
on public.waitlist (created_at desc);

create index if not exists waitlist_email_idx
on public.waitlist (lower(email));

alter table public.waitlist enable row level security;

drop policy if exists "Anyone can join waitlist" on public.waitlist;
create policy "Anyone can join waitlist" on public.waitlist
for insert
with check (
  email <> ''
  and industry <> ''
  and use_case <> ''
);

drop policy if exists "Service role can manage waitlist" on public.waitlist;
create policy "Service role can manage waitlist" on public.waitlist
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

notify pgrst, 'reload schema';
