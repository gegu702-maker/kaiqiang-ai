# P2.7 Stable Report

Date: 2026-06-18

## Stable Baseline

- Railway API deployment: `ecd0bc38-0d13-4569-80df-cc16c63df679`
- Railway deployed commit: `89e785c98714e9a137a3257ce63c24b06ac0d360`
- Railway `/health`: `200 {"status":"ok"}`
- Vercel Production deployment: `dpl_14aByR4b1pESqYvaYgAfiAi5U9JG`
- Vercel Production commit: `c5d7863820dffeb8bfcc8bb56fb8bad80e39ae27`
- `origin/master`: `c5d7863820dffeb8bfcc8bb56fb8bad80e39ae27`

## P2.7.1 Stable Railway API Baseline

- Railway API deployment: `0fb64180-2faf-4458-af20-9a6b63a5f273`
- Railway deployed commit: `84a2023972ff73089552ccb27c812e547c9425f0`
- Previous Railway deployment: `ecd0bc38-0d13-4569-80df-cc16c63df679` is `REMOVED`.
- Image digest: `sha256:97876a990be67dacd207d8cf5bc1f4af5adde56ba49a80a2a3fd9ba08fd58e25`
- Railway `/health`:
  - `STATUS=200`
  - `{"status":"ok"}`
- Railway `/api/avatar/health`:
  - `STATUS=200`
  - `{"status":"ok","musetalk":{"status":"ok","engine":"musetalk","root":"/root/MuseTalk","status_code":200,"configured_host":"u1032685-8547-93ee30c2.nmb2.seetacloud.com"}}`

P2.7.1 deployed changes:

- AutoDL / MuseTalk health hardening is live on the Railway API.
- `AUTODL_AUTO_START_ENABLED` defaults to `false`.
- `/api/avatar/health` now returns explicit MuseTalk health details.
- MuseTalk health `404`, HTML, or non-JSON responses should no longer be reported as `{}`.
- No real avatar generation smoke was run for this deployment to avoid consuming Railway or GPU trial resources.

P2.7.1 deployment scope:

- Railway deployed: YES
- Vercel deployed: NO
- DB modified: NO
- SQL executed: NO
- P2.7 Viral Analyzer quota touched: NO
- Subtitles touched: NO
- Architecture or server migration: NO

## Completed In P2.7

- Viral Analyzer temporary quota override is live on the Railway API.
- `public.viral_quota_overrides` has been created.
- Two free test accounts each have `extra_monthly_limit=50`.
- The test accounts remain on `profiles.plan=free`.
- `/studio/viral-analyzer` has been manually verified successfully.
- `/studio/avatar` has been manually verified successfully for digital human generation.
- The latest generated MP4 is accessible and returns `video/mp4`.

## DB State

- `profiles.plan` was not changed for the test accounts.
- `usage_logs` was not cleared.
- `user_quotas` was not touched for Viral Analyzer quota.
- `524737637@qq.com` current monthly Viral Analyzer used count: `7`.
- `373433501@qq.com` still has active extra Viral Analyzer quota.
- Temporary quota `expires_at`: `2026-07-18T06:20:11Z`.

## AutoDL / MuseTalk State

- AutoDL has been manually powered on.
- AutoDL internal health is OK:
  - `http://127.0.0.1:6006/health`
  - `{"status":"ok","engine":"musetalk","root":"/root/MuseTalk"}`
- Railway `MUSE_TALK_API_BASE_URL` public health is OK.
- `/studio/avatar` generation has been manually verified successfully.
- Unsupported normal-instance AutoDL automatic `power_on` remains a risk if MuseTalk public health is not already OK.

## Risks

- AutoDL normal-instance automatic `power_on` may still fail.
- `/api/avatar/health` may be misleading for 404 or non-JSON MuseTalk responses.
- Avatar task `error_message` values can be too long when upstream failures are nested.
- Generated videos currently do not include subtitles; subtitles are a P2.8 follow-up, not part of this stable baseline.
- Railway CLI token and deployment workflow should be stabilized and documented.
- Railway trial and payment risk remains because the current user cannot upgrade with an overseas payment card.

## Next Recommended Actions

- P2.7 follow-up hardening: improve AutoDL health behavior and auto-start gating.
- Consider `AUTODL_AUTO_START_ENABLED=false` for normal/non-pro AutoDL instances unless a supported API path is confirmed.
- Fix `/api/avatar/health` so unhealthy MuseTalk responses are explicit.
- Track subtitles as P2.8 and do not mix subtitle work into the current stable version.
- Track infra payment / domestic deploy fallback as a separate P2.8 workstream.
- Do not mix subtitle work or infrastructure migration into the current stable version.
