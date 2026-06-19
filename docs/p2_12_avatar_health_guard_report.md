# P2.12 Avatar Health Guard Stable Report

## Goal

P2.12 prevents users from submitting Avatar Studio generation jobs when the MuseTalk avatar service is not ready.

Before this phase, `/studio/avatar` could still submit a generation request while MuseTalk was unhealthy. The backend then created an `avatar_tasks` row and marked it `failed`, even though the problem was infrastructure readiness rather than user input, quota, subtitles, or database state.

## Baseline

- Starting ref: `stable-p2.9-avatar-studio-ux-2026-06-18`
- Starting commit: `6cc6094c60964ec84501a9d0421a89c2f895f0b2`
- P2.12 branch: `codex/p2-12-avatar-health-guard`
- P2.12 commit: `46f86d9a871e7ec43d8e2a04ecc38aee471ac85d`

## Production Deployment

- Vercel Production deployment: `dpl_DVHSXCnjybgkRmzQBopRXLYeKLYt`
- Production URL: [https://kaiqiang.ai](https://kaiqiang.ai/)
- Railway deployment: not required

## Scope

Modified file:

- `apps/web/components/AvatarVideoGenerator.tsx`

No backend, database, quota, billing, pricing, header, subtitle, MuseTalk, AutoDL, or Viral Analyzer code was changed.

## Implementation

- Added Avatar Studio service health state:
  - `checking`
  - `ready`
  - `unavailable`
- Added page-load health check using the existing backend endpoint:
  - `GET /api/avatar/health`
- Treats these `payload.musetalk.status` values as ready:
  - `ok`
  - `ready`
  - `healthy`
  - `success`
- Shows service status copy:
  - `正在检查数字人生成服务状态...`
  - `数字人生成服务已就绪。`
  - `数字人生成服务暂未就绪，请稍后再试或联系管理员。`
- Adds a `重新检查服务状态` button when the service is unavailable.
- Disables the generate button unless the avatar service is ready.
- Adds a submit-time guard at the beginning of `handleGenerate()` so unavailable service state returns locally and does not call:
  - `/api/avatar/template-generate`
  - `/api/avatar/generate`

## Verification

- `git diff --check`: PASS
- `npm run lint`: PASS
- Local `npm run build`: compiled and type-checked successfully, then local prerender of `/studio` failed because Supabase browser environment variables were missing. No env or code changes were made for local build.
- Vercel Preview deployment: READY
- Vercel Production deployment: READY

## Production Smoke

- `https://kaiqiang.ai/pricing`: PASS, returned `200`
- `/pricing` plan labels: PASS, contains `Free`, `Plus`, `Pro`, `Business`
- `https://kaiqiang.ai/studio/avatar` unauthenticated: PASS, returned `307` to `/login?next=/studio/avatar`

## Logged-In Visual Confirmation

User confirmed the Production logged-in `/studio/avatar` experience:

- service health UI appears
- page displays `数字人生成服务已就绪。`
- generate button is available when MuseTalk is healthy
- recent task list still shows `自动字幕`

## Real Generation Recovery Confirmation

After AutoDL / MuseTalk was manually restored, user confirmed a real Production generation succeeded:

- AutoDL local `http://127.0.0.1:6006/health`: OK
- SeetaCloud public `https://u1032685-8547-93ee30c2.nmb2.seetacloud.com:8443/health`: OK
- Railway `https://api.kaiqiang.ai/api/avatar/health`: OK
- latest avatar task: `completed`
- quota changed from `20/999999` used to `21/999999` used

## AutoDL / MuseTalk Incident Review

The failed Production task was:

- task_id: `393616c2-f7a1-4452-a781-e5d0c8270d48`
- error: `MuseTalk 服务未就绪，请先手动启动 AutoDL / MuseTalk 后重试。 (musetalk_not_ready_manual_start_required)`

Root cause:

- The failure was not caused by frontend code, quota, subtitles, billing, or database state.
- Railway API itself was healthy at `/health`.
- Railway `/api/avatar/health` reported MuseTalk unhealthy because the configured public MuseTalk endpoint returned a 404 HTML response instead of a healthy MuseTalk `/health` JSON response.
- This indicated the AutoDL / MuseTalk public mapping was not ready.

Recovery path:

- Confirmed MuseTalk locally inside AutoDL on port `6006`.
- Confirmed SeetaCloud public `8443` health.
- Confirmed Railway `/api/avatar/health` returned healthy after the public mapping recovered.

## Value

P2.12 adds a frontend safety gate before expensive avatar generation. If MuseTalk is not ready, users now see service status feedback and the generate button is disabled, avoiding avoidable failed `avatar_tasks` rows and confusing failed-task UX.

## Untouched Areas

- Railway deployed: NO
- Vercel deployed after this archive step: NO
- DB modified: NO
- SQL executed: NO
- `profiles.plan` modified: NO
- `usage_logs` modified: NO
- `user_quotas` touched: NO
- billing / stripe touched: NO
- pricing plan benefits touched: NO
- header touched: NO
- P2.7 Viral Analyzer quota touched: NO
- subtitle backend touched: NO
- MuseTalk / AutoDL code touched: NO
- master merged: NO
- `p2-2-b-preview` dirty branch touched: NO
- new GPU generation triggered during archive: NO
