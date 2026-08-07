-- P2.37 PREVIEW ONLY rollback draft.
-- DESTRUCTIVE: execute only with separate explicit rollback authorization.

begin;

drop policy if exists "Service role manages preview viral artifacts" on storage.objects;
drop policy if exists "Service role manages viral job stages" on public.viral_analysis_job_stage_runs;
drop policy if exists "Service role manages viral jobs" on public.viral_analysis_jobs;
drop policy if exists "Users read only their own viral jobs" on public.viral_analysis_jobs;

drop function if exists public.claim_viral_analysis_cleanup(text, integer);
drop function if exists public.finish_viral_analysis_cleanup(
  uuid, text, bigint, boolean, boolean, boolean, boolean, boolean
);
drop function if exists public.finish_viral_analysis_stage(
  uuid, text, bigint, text, text, text, integer, text, text, jsonb, text,
  text, jsonb, jsonb, jsonb, text, text, text, boolean, timestamptz, bigint
);
drop function if exists public.heartbeat_viral_analysis_job(uuid, text, bigint, integer);
drop function if exists public.checkpoint_viral_analysis_job(uuid, text, bigint, text, jsonb, integer);
drop function if exists public.claim_viral_analysis_job(text, integer);
drop function if exists public.request_cancel_viral_analysis_job(uuid, uuid);
drop function if exists public.create_or_reuse_viral_analysis_job(uuid, text, text, text, text, text);

drop trigger if exists set_viral_stage_runs_updated_at on public.viral_analysis_job_stage_runs;
drop trigger if exists set_viral_analysis_jobs_updated_at on public.viral_analysis_jobs;
drop function if exists public.set_viral_job_updated_at();

drop table if exists public.viral_analysis_job_stage_runs;
drop table if exists public.viral_analysis_jobs;

commit;
