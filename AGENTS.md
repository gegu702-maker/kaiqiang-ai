# kaiqiang.ai Agent Guardrails

These rules apply to AI Agent / Codex work in this repository.

## Start-of-Task Baseline

- Before every task, run a read-only baseline audit.
- Required baseline commands:
  - `pwd`
  - `git status --short`
  - `git branch --show-current`
  - `git rev-parse HEAD`
  - `git log -1 --oneline`
  - `git remote -v`
- Do not modify files during the baseline audit.

## Dirty Workspace Guard

- Do not blindly develop on a dirty workspace.
- If dirty files are unrelated to the task, stop and report them.
- If dirty files may belong to the task, explain the basis for that judgment before continuing.
- Do not clean, delete, stash, reset, overwrite, or discard files without explicit user confirmation.
- Do not mix unrelated dirty files into a task commit.

## Protected Areas

By default, do not modify these areas unless the user explicitly requests it:

- billing, Stripe, quota, or auth behavior
- Supabase schema or database migrations
- Production database data or structure
- environment variables or secret handling

## Deployment and Runtime Restrictions

- Do not deploy to Production unless the user explicitly requests it.
- Do not execute SQL unless the user explicitly requests it.
- Do not trigger real GPU, AutoDL, MuseTalk, or video generation unless the user explicitly requests it.
- Prefer dry-run, read-only, mock, or documentation-only work when the request does not require live side effects.

## End-of-Task Report

Every completed task must report:

- modified files
- test results
- whether deployment was performed
- whether the database was changed
- whether GPU, AutoDL, MuseTalk, or video generation was triggered
- known risks
- recommended next steps
