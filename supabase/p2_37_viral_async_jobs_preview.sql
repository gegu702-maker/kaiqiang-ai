-- P2.37 PREVIEW ONLY: durable async viral-analysis jobs.
-- Authorized target project ref: saqloovjtyllajuzeccr
-- Never execute against any Production project.

begin;

create table public.viral_analysis_jobs (
  id uuid primary key default gen_random_uuid(),
  request_id text not null unique check (length(request_id) between 8 and 128),
  user_id uuid not null references auth.users(id) on delete cascade,
  file_fingerprint text not null check (file_fingerprint ~ '^[0-9a-f]{64}$'),
  parameter_version text not null check (length(parameter_version) between 1 and 128),
  analysis_params_hash text not null check (analysis_params_hash ~ '^[0-9a-f]{64}$'),
  pipeline_version text not null check (length(pipeline_version) between 1 and 128),
  status text not null default 'uploading' check (status in (
    'uploading', 'pending', 'running', 'retry_wait', 'cancel_requested',
    'succeeded', 'failed', 'cancelled'
  )),
  stage text not null default 'media_received',
  progress integer not null default 0 check (progress between 0 and 100),
  attempt integer not null default 0 check (attempt >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  revision bigint not null default 0 check (revision >= 0),
  lease_owner text check (lease_owner is null or length(lease_owner) <= 128),
  lease_expires_at timestamptz,
  heartbeat_at timestamptz,
  input_bucket text,
  input_object_path text,
  artifact_manifest jsonb not null default '{}'::jsonb
    check (octet_length(artifact_manifest::text) <= 524288),
  checkpoint_stage text,
  checkpoint jsonb check (
    checkpoint is null or octet_length(checkpoint::text) <= 4194304
  ),
  result jsonb check (result is null or octet_length(result::text) <= 2097152),
  quality jsonb check (quality is null or octet_length(quality::text) <= 524288),
  provenance jsonb check (provenance is null or octet_length(provenance::text) <= 524288),
  error_class text,
  error_code text,
  safe_error_message text check (
    safe_error_message is null or length(safe_error_message) <= 2000
  ),
  retryable boolean not null default false,
  next_retry_at timestamptz,
  cancel_requested_at timestamptz,
  stage_started_at timestamptz,
  stage_finished_at timestamptz,
  stage_elapsed_ms bigint,
  input_expires_at timestamptz,
  checkpoint_expires_at timestamptz,
  result_expires_at timestamptz,
  purge_after timestamptz,
  cleanup_lease_owner text check (
    cleanup_lease_owner is null or length(cleanup_lease_owner) <= 128
  ),
  cleanup_lease_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  usage_recorded boolean not null default false
);

create table public.viral_analysis_job_stage_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.viral_analysis_jobs(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  stage text not null,
  attempt integer not null check (attempt >= 1),
  status text not null check (status in ('running', 'succeeded', 'failed', 'cancelled')),
  worker_owner text not null check (length(worker_owner) <= 128),
  input_version text not null,
  output_version text,
  checkpoint jsonb check (
    checkpoint is null or octet_length(checkpoint::text) <= 4194304
  ),
  checkpoint_object_path text,
  output_sha256 text,
  error_class text,
  error_code text,
  safe_error_message text check (
    safe_error_message is null or length(safe_error_message) <= 2000
  ),
  retryable boolean not null default false,
  started_at timestamptz not null default now(),
  heartbeat_at timestamptz,
  finished_at timestamptz,
  elapsed_ms bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (job_id, stage, attempt)
);

create unique index viral_jobs_reusable_identity_uidx
on public.viral_analysis_jobs (user_id, file_fingerprint, parameter_version)
where status in (
  'uploading', 'pending', 'running', 'retry_wait', 'cancel_requested', 'succeeded'
);

create index viral_jobs_claim_idx
on public.viral_analysis_jobs (status, next_retry_at, lease_expires_at, created_at);

create index viral_jobs_cleanup_idx
on public.viral_analysis_jobs (
  input_expires_at, checkpoint_expires_at, result_expires_at, purge_after
);

create index viral_stage_runs_job_idx
on public.viral_analysis_job_stage_runs (job_id, created_at);

create function public.set_viral_job_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger set_viral_analysis_jobs_updated_at
before update on public.viral_analysis_jobs
for each row execute function public.set_viral_job_updated_at();

create trigger set_viral_stage_runs_updated_at
before update on public.viral_analysis_job_stage_runs
for each row execute function public.set_viral_job_updated_at();

create function public.create_or_reuse_viral_analysis_job(
  p_user_id uuid,
  p_request_id text,
  p_file_fingerprint text,
  p_parameter_version text,
  p_analysis_params_hash text,
  p_pipeline_version text
)
returns table (job_id uuid, reused boolean, job_status text)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job public.viral_analysis_jobs%rowtype;
begin
  perform pg_advisory_xact_lock(hashtextextended(
    p_user_id::text || ':' || p_file_fingerprint || ':' || p_parameter_version,
    0
  ));

  update public.viral_analysis_jobs
  set status = 'failed',
      error_class = 'upload',
      error_code = 'upload_abandoned',
      safe_error_message = '上传会话已过期，可安全创建新任务。',
      retryable = true,
      completed_at = now(),
      input_expires_at = now(),
      checkpoint_expires_at = now(),
      purge_after = now() + interval '1 hour',
      revision = revision + 1
  where user_id = p_user_id
    and file_fingerprint = p_file_fingerprint
    and parameter_version = p_parameter_version
    and status = 'uploading'
    and created_at <= now() - interval '15 minutes';

  select * into v_job
  from public.viral_analysis_jobs
  where user_id = p_user_id
    and file_fingerprint = p_file_fingerprint
    and parameter_version = p_parameter_version
    and status in (
      'uploading', 'pending', 'running', 'retry_wait', 'cancel_requested', 'succeeded'
    )
  order by created_at desc
  limit 1;

  if found then
    return query select v_job.id, true, v_job.status;
    return;
  end if;

  insert into public.viral_analysis_jobs (
    request_id, user_id, file_fingerprint, parameter_version,
    analysis_params_hash, pipeline_version, status, stage,
    input_expires_at, purge_after
  ) values (
    p_request_id, p_user_id, p_file_fingerprint, p_parameter_version,
    p_analysis_params_hash, p_pipeline_version, 'uploading', 'media_received',
    now() + interval '1 hour', now() + interval '1 hour'
  ) returning * into v_job;

  return query select v_job.id, false, v_job.status;
end;
$$;

create function public.claim_viral_analysis_job(
  p_worker_owner text,
  p_lease_seconds integer default 60
)
returns setof public.viral_analysis_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  return query
  with candidate as (
    select j.id
    from public.viral_analysis_jobs j
    where j.attempt < j.max_attempts
      and (
        j.status = 'pending'
        or (j.status = 'retry_wait' and coalesce(j.next_retry_at, now()) <= now())
        or (
          j.status in ('running', 'cancel_requested')
          and (j.lease_expires_at is null or j.lease_expires_at <= now())
        )
      )
    order by coalesce(j.next_retry_at, j.created_at), j.created_at
    for update skip locked
    limit 1
  )
  update public.viral_analysis_jobs j
  set status = case when j.status = 'cancel_requested' then j.status else 'running' end,
      attempt = j.attempt + 1,
      lease_owner = p_worker_owner,
      lease_expires_at = now() + interval '1 second' * greatest(p_lease_seconds, 15),
      heartbeat_at = now(),
      stage_started_at = coalesce(j.stage_started_at, now()),
      revision = j.revision + 1
  from candidate
  where j.id = candidate.id
  returning j.*;
end;
$$;

create function public.request_cancel_viral_analysis_job(
  p_job_id uuid,
  p_user_id uuid
)
returns setof public.viral_analysis_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  return query
  update public.viral_analysis_jobs j
  set status = case
        when j.status in ('succeeded', 'failed', 'cancelled') then j.status
        else 'cancel_requested' end,
      cancel_requested_at = case
        when j.status in ('succeeded', 'failed', 'cancelled') then j.cancel_requested_at
        else now() end,
      revision = case
        when j.status in ('succeeded', 'failed', 'cancelled') then j.revision
        else j.revision + 1 end
  where j.id = p_job_id
    and j.user_id = p_user_id
  returning j.*;
end;
$$;

create function public.heartbeat_viral_analysis_job(
  p_job_id uuid,
  p_worker_owner text,
  p_expected_revision bigint,
  p_lease_seconds integer default 60
)
returns table (accepted boolean, new_revision bigint, observed_status text)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_revision bigint;
  v_status text;
begin
  update public.viral_analysis_jobs
  set heartbeat_at = now(),
      lease_expires_at = now() + interval '1 second' * greatest(p_lease_seconds, 15),
      revision = revision + 1
  where id = p_job_id
    and lease_owner = p_worker_owner
    and revision = p_expected_revision
    and lease_expires_at > now()
    and status in ('running', 'cancel_requested')
  returning revision, status into v_revision, v_status;

  if found then
    return query select true, v_revision, v_status;
  else
    select status into v_status from public.viral_analysis_jobs where id = p_job_id;
    return query select false, null::bigint, v_status;
  end if;
end;
$$;

create function public.checkpoint_viral_analysis_job(
  p_job_id uuid,
  p_worker_owner text,
  p_expected_revision bigint,
  p_stage text,
  p_checkpoint jsonb,
  p_lease_seconds integer default 60
)
returns table (accepted boolean, new_revision bigint, observed_status text)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job public.viral_analysis_jobs%rowtype;
  v_revision bigint;
begin
  if p_checkpoint is null or octet_length(p_checkpoint::text) > 4194304 then
    raise exception 'checkpoint size is invalid';
  end if;

  select * into v_job
  from public.viral_analysis_jobs
  where id = p_job_id
  for update;

  if not found
     or v_job.lease_owner is distinct from p_worker_owner
     or v_job.revision <> p_expected_revision
     or v_job.lease_expires_at <= now()
     or v_job.status not in ('running', 'cancel_requested') then
    return query select false, null::bigint, v_job.status;
    return;
  end if;

  if v_job.stage is distinct from p_stage then
    insert into public.viral_analysis_job_stage_runs (
      job_id, user_id, stage, attempt, status, worker_owner,
      input_version, output_version, retryable,
      started_at, heartbeat_at, finished_at, elapsed_ms
    ) values (
      v_job.id, v_job.user_id, v_job.stage, v_job.attempt, 'succeeded',
      p_worker_owner, v_job.pipeline_version, v_job.pipeline_version, false,
      coalesce(v_job.stage_started_at, now()), v_job.heartbeat_at, now(),
      greatest(0, round(extract(epoch from (now() - coalesce(v_job.stage_started_at, now()))) * 1000))::bigint
    ) on conflict (job_id, stage, attempt) do nothing;
  end if;

  update public.viral_analysis_jobs
  set stage = p_stage,
      progress = greatest(progress, case p_stage
        when 'a_primary_generation' then 68
        when 'a_fact_review' then 76
        when 'a_targeted_repair' then 84
        when 'optional_variants' then 91
        else progress end),
      checkpoint_stage = p_stage,
      checkpoint = p_checkpoint,
      heartbeat_at = now(),
      lease_expires_at = now() + interval '1 second' * greatest(p_lease_seconds, 15),
      stage_finished_at = case when stage is distinct from p_stage then now() else stage_finished_at end,
      stage_started_at = case when stage is distinct from p_stage then now() else stage_started_at end,
      revision = revision + 1
  where id = p_job_id
  returning revision into v_revision;

  return query select true, v_revision, v_job.status;
end;
$$;

create function public.finish_viral_analysis_stage(
  p_job_id uuid,
  p_worker_owner text,
  p_expected_revision bigint,
  p_outcome text,
  p_next_status text,
  p_next_stage text,
  p_progress integer,
  p_input_version text,
  p_output_version text,
  p_checkpoint jsonb,
  p_checkpoint_object_path text,
  p_output_sha256 text,
  p_result jsonb,
  p_quality jsonb,
  p_provenance jsonb,
  p_error_class text,
  p_error_code text,
  p_safe_error_message text,
  p_retryable boolean,
  p_next_retry_at timestamptz,
  p_elapsed_ms bigint
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job public.viral_analysis_jobs%rowtype;
  v_terminal boolean;
begin
  if p_outcome not in ('succeeded', 'failed', 'cancelled') then
    raise exception 'invalid stage outcome';
  end if;

  select * into v_job
  from public.viral_analysis_jobs
  where id = p_job_id
  for update;

  if not found
     or v_job.lease_owner is distinct from p_worker_owner
     or v_job.revision <> p_expected_revision
     or v_job.lease_expires_at <= now()
     or v_job.status not in ('running', 'cancel_requested') then
    return false;
  end if;

  insert into public.viral_analysis_job_stage_runs (
    job_id, user_id, stage, attempt, status, worker_owner,
    input_version, output_version, checkpoint, checkpoint_object_path,
    output_sha256, error_class, error_code, safe_error_message,
    retryable, started_at, heartbeat_at, finished_at, elapsed_ms
  ) values (
    v_job.id, v_job.user_id, v_job.stage, v_job.attempt, p_outcome,
    p_worker_owner, p_input_version, p_output_version, null,
    coalesce(p_checkpoint_object_path, 'inline:viral_analysis_jobs/' || v_job.id::text),
    p_output_sha256, p_error_class, p_error_code,
    left(p_safe_error_message, 2000), p_retryable,
    coalesce(v_job.stage_started_at, now()), v_job.heartbeat_at, now(), p_elapsed_ms
  );

  v_terminal := p_next_status in ('succeeded', 'failed', 'cancelled');

  if p_next_status = 'succeeded' and not v_job.usage_recorded then
    insert into public.usage_logs (user_id, action, quantity, period_start)
    values (v_job.user_id, 'viral_analyze', 1, date_trunc('month', now()));
  end if;

  update public.viral_analysis_jobs
  set status = p_next_status,
      stage = p_next_stage,
      progress = greatest(progress, least(greatest(p_progress, 0), 100)),
      checkpoint_stage = case when p_outcome = 'succeeded' then v_job.stage else checkpoint_stage end,
      checkpoint = coalesce(p_checkpoint, checkpoint),
      result = coalesce(p_result, result),
      quality = coalesce(p_quality, quality),
      provenance = coalesce(p_provenance, provenance),
      error_class = p_error_class,
      error_code = p_error_code,
      safe_error_message = left(p_safe_error_message, 2000),
      retryable = p_retryable,
      next_retry_at = p_next_retry_at,
      stage_finished_at = now(),
      stage_elapsed_ms = p_elapsed_ms,
      stage_started_at = case when v_terminal then null else now() end,
      completed_at = case when v_terminal then now() else completed_at end,
      usage_recorded = case when p_next_status = 'succeeded' then true else usage_recorded end,
      input_expires_at = case
        when p_next_status = 'succeeded' then now() + interval '24 hours'
        when p_next_status in ('failed', 'cancelled') then now() + interval '1 hour'
        else input_expires_at end,
      checkpoint_expires_at = case when v_terminal then now() + interval '7 days' else checkpoint_expires_at end,
      result_expires_at = case when p_next_status = 'succeeded' then now() + interval '30 days' else result_expires_at end,
      purge_after = case when v_terminal then now() + interval '30 days' else purge_after end,
      lease_owner = case when p_next_status = 'running' then lease_owner else null end,
      lease_expires_at = case when p_next_status = 'running' then now() + interval '60 seconds' else null end,
      revision = revision + 1
  where id = v_job.id;

  return true;
end;
$$;

create function public.claim_viral_analysis_cleanup(
  p_worker_owner text,
  p_lease_seconds integer default 120
)
returns setof public.viral_analysis_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  return query
  with candidate as (
    select j.id
    from public.viral_analysis_jobs j
    where j.status in ('uploading', 'succeeded', 'failed', 'cancelled')
      and (
        (j.input_expires_at is not null and j.input_expires_at <= now())
        or (j.checkpoint_expires_at is not null and j.checkpoint_expires_at <= now())
        or (j.result_expires_at is not null and j.result_expires_at <= now())
        or (j.purge_after is not null and j.purge_after <= now())
      )
      and (j.cleanup_lease_expires_at is null or j.cleanup_lease_expires_at <= now())
    order by j.updated_at
    for update skip locked
    limit 1
  )
  update public.viral_analysis_jobs j
  set cleanup_lease_owner = p_worker_owner,
      cleanup_lease_expires_at = now() + interval '1 second' * greatest(p_lease_seconds, 30),
      revision = j.revision + 1
  from candidate
  where j.id = candidate.id
  returning j.*;
end;
$$;

create function public.finish_viral_analysis_cleanup(
  p_job_id uuid,
  p_worker_owner text,
  p_expected_revision bigint,
  p_clear_input boolean,
  p_clear_checkpoint boolean,
  p_clear_result boolean,
  p_purge boolean,
  p_success boolean
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_job public.viral_analysis_jobs%rowtype;
begin
  select * into v_job
  from public.viral_analysis_jobs
  where id = p_job_id
  for update;

  if not found
     or v_job.cleanup_lease_owner is distinct from p_worker_owner
     or v_job.revision <> p_expected_revision
     or v_job.cleanup_lease_expires_at <= now() then
    return false;
  end if;

  if not p_success then
    update public.viral_analysis_jobs
    set cleanup_lease_owner = null,
        cleanup_lease_expires_at = now() + interval '5 minutes',
        revision = revision + 1
    where id = p_job_id;
    return true;
  end if;

  if p_purge then
    delete from public.viral_analysis_jobs where id = p_job_id;
    return true;
  end if;

  update public.viral_analysis_jobs
  set input_bucket = case when p_clear_input then null else input_bucket end,
      input_object_path = case when p_clear_input then null else input_object_path end,
      input_expires_at = case when p_clear_input then null else input_expires_at end,
      checkpoint_stage = case when p_clear_checkpoint then null else checkpoint_stage end,
      checkpoint = case when p_clear_checkpoint then null else checkpoint end,
      checkpoint_expires_at = case when p_clear_checkpoint then null else checkpoint_expires_at end,
      result = case when p_clear_result then null else result end,
      quality = case when p_clear_result then null else quality end,
      provenance = case when p_clear_result then null else provenance end,
      result_expires_at = case when p_clear_result then null else result_expires_at end,
      cleanup_lease_owner = null,
      cleanup_lease_expires_at = null,
      revision = revision + 1
  where id = p_job_id;
  return true;
end;
$$;

alter table public.viral_analysis_jobs enable row level security;
alter table public.viral_analysis_job_stage_runs enable row level security;

revoke all on public.viral_analysis_jobs from anon, authenticated;
revoke all on public.viral_analysis_job_stage_runs from anon, authenticated;

grant select (
  id, request_id, user_id, file_fingerprint, parameter_version,
  status, stage, progress, attempt, retryable, next_retry_at,
  error_class, error_code, safe_error_message,
  stage_started_at, stage_finished_at, stage_elapsed_ms,
  quality, provenance, result, created_at, updated_at, completed_at
) on public.viral_analysis_jobs to authenticated;

grant all on public.viral_analysis_jobs to service_role;
grant all on public.viral_analysis_job_stage_runs to service_role;

create policy "Users read only their own viral jobs"
on public.viral_analysis_jobs
for select to authenticated
using (auth.uid() = user_id);

create policy "Service role manages viral jobs"
on public.viral_analysis_jobs
for all to service_role
using (true) with check (true);

create policy "Service role manages viral job stages"
on public.viral_analysis_job_stage_runs
for all to service_role
using (true) with check (true);

revoke all on function public.create_or_reuse_viral_analysis_job(uuid, text, text, text, text, text)
from public, anon, authenticated;
revoke all on function public.claim_viral_analysis_job(text, integer)
from public, anon, authenticated;
revoke all on function public.request_cancel_viral_analysis_job(uuid, uuid)
from public, anon, authenticated;
revoke all on function public.heartbeat_viral_analysis_job(uuid, text, bigint, integer)
from public, anon, authenticated;
revoke all on function public.checkpoint_viral_analysis_job(uuid, text, bigint, text, jsonb, integer)
from public, anon, authenticated;
revoke all on function public.finish_viral_analysis_stage(
  uuid, text, bigint, text, text, text, integer, text, text, jsonb, text,
  text, jsonb, jsonb, jsonb, text, text, text, boolean, timestamptz, bigint
) from public, anon, authenticated;
revoke all on function public.claim_viral_analysis_cleanup(text, integer)
from public, anon, authenticated;
revoke all on function public.finish_viral_analysis_cleanup(
  uuid, text, bigint, boolean, boolean, boolean, boolean, boolean
) from public, anon, authenticated;

grant execute on function public.create_or_reuse_viral_analysis_job(uuid, text, text, text, text, text)
to service_role;
grant execute on function public.claim_viral_analysis_job(text, integer)
to service_role;
grant execute on function public.request_cancel_viral_analysis_job(uuid, uuid)
to service_role;
grant execute on function public.heartbeat_viral_analysis_job(uuid, text, bigint, integer)
to service_role;
grant execute on function public.checkpoint_viral_analysis_job(uuid, text, bigint, text, jsonb, integer)
to service_role;
grant execute on function public.finish_viral_analysis_stage(
  uuid, text, bigint, text, text, text, integer, text, text, jsonb, text,
  text, jsonb, jsonb, jsonb, text, text, text, boolean, timestamptz, bigint
) to service_role;
grant execute on function public.claim_viral_analysis_cleanup(text, integer)
to service_role;
grant execute on function public.finish_viral_analysis_cleanup(
  uuid, text, bigint, boolean, boolean, boolean, boolean, boolean
) to service_role;

-- The bucket itself is created separately through the Storage API as private.
-- With no anon/authenticated storage.objects policy, RLS denies direct access.
create policy "Service role manages preview viral artifacts"
on storage.objects
for all to service_role
using (bucket_id = 'viral-job-artifacts-preview')
with check (bucket_id = 'viral-job-artifacts-preview');

commit;
