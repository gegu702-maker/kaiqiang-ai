# Dirty Worktree Guard SOP

## Applicable Scenario

Use this SOP whenever `git status --short` is not clean.

## Rules

1. If dirty files are unrelated to the current task, stop development and report them.
2. If dirty files may belong to the current task, explain the judgment basis before continuing.
3. Without explicit user confirmation, do not clean, delete, stash, reset, overwrite, or discard any file.
4. Do not include unrelated dirty files in the current commit.

## Required Output Format

```text
dirty files:
related / unrelated assessment:
risk:
recommended next step:
```

## Assessment Guidance

- Treat modified business code, configuration, generated files, migrations, and environment files as high risk unless the task explicitly targets them.
- Treat untracked files as user-owned until proven otherwise.
- If ownership or relevance is unclear, stop and ask for confirmation.
- Keep any later commit limited to files intentionally changed for the current task.
