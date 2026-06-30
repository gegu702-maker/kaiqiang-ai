# Production Release Smoke SOP

## Applicable Scenario

Use this SOP only when the user explicitly requests a Production release.

## Rules

1. Do not release to Production by default.
2. Confirm the target commit before releasing.
3. After release, record the Vercel deployment ID and Railway deployment ID. If either platform was not involved, write `Not touched`.
4. Verify the Production URL after release.
5. State whether the release changed the database, executed a migration, or affected billing, quota, or auth.

## Required Output Format

```text
target commit:
production URL:
Vercel deployment:
Railway deployment:
DB migration:
smoke checks:
changed areas:
untouched areas:
known risks:
final verdict:
```

## Smoke Check Guidance

- Confirm the deployed commit matches the approved target commit.
- Check the Production URL loads successfully.
- Record failures, partial checks, or skipped checks explicitly.
- If database, billing, quota, or auth behavior was untouched, say so directly.
- If a deployment platform was not part of the release, record `Not touched` rather than leaving it blank.
