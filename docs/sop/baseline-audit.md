# Baseline Audit SOP

## Applicable Scenario

Use this SOP before every development task. The goal is to understand the repository state before making any change.

## Read-Only Commands

Run these commands exactly as read-only checks:

```bash
pwd
git status --short
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
git remote -v
```

These checks must not modify files, create generated output, update dependencies, deploy services, run migrations, or change environment state.

## Required Output Format

```text
current directory:
branch:
HEAD:
latest commit:
dirty state:
risk summary:
whether it is safe to continue:
```

## Evaluation Rules

- If `git status --short` is empty, record the workspace as clean.
- If `git status --short` is not empty, record the workspace as dirty and apply `dirty-worktree-guard.md`.
- If the current directory, branch, or HEAD is unexpected, stop and report the mismatch.
- Continue only when the workspace state is understood and the risk summary supports the requested task.
