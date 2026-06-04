# Kaiqiang.ai Production Status - 2026-06

## Architecture

```text
User
  -> Vercel frontend
  -> Railway API
  -> AutoDL MuseTalk GPU service
  -> Supabase Storage
```

## Key Domains

- `https://kaiqiang.ai` - production frontend
- `https://api.kaiqiang.ai` - production API
- `https://api.kaiqiang.ai/docs` - FastAPI Swagger
- `https://kaiqiang.ai/studio/avatar` - MuseTalk avatar studio

## Key Environment Variables

### Vercel Frontend

- `NEXT_PUBLIC_API_URL` - public Railway API base URL used by browser requests.
- `SERVER_API_URL` - Railway API base URL used by server-side frontend code.
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL for browser/server auth.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase public anon key for auth.
- `NEXT_PUBLIC_SITE_URL` - public frontend URL for auth redirects.
- `ADMIN_API_KEY` - admin API header value for admin-only frontend actions.
- `NEXT_PUBLIC_POSTHOG_KEY` - PostHog browser analytics key.
- `NEXT_PUBLIC_POSTHOG_HOST` - PostHog ingestion host.

### Railway API

- `SUPABASE_URL` - Supabase project URL used by API.
- `SUPABASE_SERVICE_ROLE_KEY` - service role key used by API for storage/database writes.
- `SUPABASE_IMAGE_BUCKET` - product/avatar image bucket name.
- `SUPABASE_VOICE_BUCKET` - input/generated voice bucket name.
- `SUPABASE_VIDEO_BUCKET` - input/result video bucket name.
- `SUPABASE_CLONED_BUCKET` - cloned voice bucket name.
- `SUPABASE_SUBTITLE_BUCKET` - subtitle bucket name.
- `MUSE_TALK_API_BASE_URL` - AutoDL 6006 custom service public URL.
- `MUSE_TALK_API_KEY` - optional MuseTalk bearer key if enabled on AutoDL.
- `MUSE_TALK_TIMEOUT_SECONDS` - timeout for MuseTalk generation requests.
- `AUTODL_API_TOKEN` - AutoDL OpenAPI token.
- `AUTODL_INSTANCE_ID` - AutoDL instance UUID.
- `AUTODL_API_BASE_URL` - AutoDL OpenAPI base URL.
- `AUTODL_START_TIMEOUT_SECONDS` - max wait time for GPU/MuseTalk readiness.
- `GPU_IDLE_SHUTDOWN_MINUTES` - idle threshold before AutoDL shutdown; currently not used while normal-container manual startup is the production validation strategy.
- `VOICE_CLONE_PROVIDER` - TTS provider selector.
- `VOLCENGINE_TTS_APP_ID` - Volcengine TTS app id.
- `VOLCENGINE_TTS_ACCESS_TOKEN` - Volcengine TTS access token.
- `VOLCENGINE_TTS_CLUSTER` - Volcengine TTS cluster.
- `VOLCENGINE_TTS_VOICE_TYPE` - default Volcengine voice type.
- `VOLCENGINE_TTS_ENDPOINT` - Volcengine TTS endpoint.
- `WEB_ORIGIN` - frontend origin for CORS.
- `CORS_ORIGINS` - comma-separated allowed browser origins.
- `PUBLIC_SITE_URL` - public frontend URL used for generated asset references.

### AutoDL

- `/root/autodl-tmp/start_musetalk.sh` - persistent MuseTalk startup script.
- `/root/autodl-tmp/idle_shutdown.sh` - AutoDL-side idle watchdog; retained but currently disabled during normal-container user validation.
- `/etc/autodl-init` - AutoDL init hook that invokes the startup script.
- `/root/autodl-tmp/musetalk_service.log` - MuseTalk FastAPI log.

## Key GitHub Commits

- `775f2db` - Wire MuseTalk into avatar studio
- `a528311` - Start MuseTalk after AutoDL power on

## Verified Features

- Vercel frontend serves `https://kaiqiang.ai/studio/avatar`.
- Login protection redirects anonymous users to `/login?next=/studio/avatar`.
- Railway API health returns `{"status":"ok"}`.
- Railway `/api/avatar/health` reaches AutoDL MuseTalk `/health`.
- AutoDL 6006 service returns `{"status":"ok","engine":"musetalk","root":"/root/MuseTalk"}`.
- `POST /api/debug/musetalk-test` generates a real MuseTalk video and uploads MP4 to Supabase Storage.
- Supabase Storage buckets are available for images, voices, videos, cloned audio, and subtitles.
- `avatar_tasks` table exists with task status, progress stage, result URL, and GPU usage timestamp fields.
- AutoDL manual startup runs `/etc/autodl-init`, which invokes `/root/autodl-tmp/start_musetalk.sh`.
- Current AutoDL production validation strategy keeps the normal container running after the administrator manually starts it, so real user tests do not fail because the developer token cannot automatically wake the container.
- `/root/autodl-tmp/idle_shutdown.sh` was previously verified to stop the AutoDL container after 10 minutes of inactivity, but it is currently disabled.

## Known Issues

- `/api/avatar/generate` is currently synchronous and waits for MuseTalk generation to finish before returning.
- A long-running browser request may appear idle while the backend is generating video.
- AutoDL custom service URLs can return an AutoDL HTML 404 if the 6006 service is not running.
- MuseTalk is currently deployed on a normal AutoDL container instance: `3ec3448547-93ee30c2`.
- Normal AutoDL container instances are not supported by the current developer token for automatic `power_on`.
- AutoDL Pro API was tested with `pro/list`; it returned success with `result_total=0` and `list=[]`, so the account currently has no Pro instance.
- Current production validation strategy: disable idle shutdown, manually start the AutoDL normal container, and keep it resident for user validation.
- Future migration path: move MuseTalk to AutoDL Pro or an independent GPU server after paid users appear, then restore automatic shutdown plus automatic wake-up.
- Volcengine TTS permissions depend on the AppID/Cluster/VoiceType combination granted in the Volcengine console.
- Local repository history has used deployment worktrees to reconcile remote master updates; always fetch latest master before pushing.

## Next Deployment Notes

- Deploy frontend from `apps/web`, not the repository root.
- Confirm Vercel production build output includes `/studio/avatar`.
- Deploy API from `apps/api` on Railway.
- Keep `MUSE_TALK_API_BASE_URL` pointed at the AutoDL custom service for port `6006`.
- After AutoDL image reset or instance replacement, recreate `/root/autodl-tmp/start_musetalk.sh`, keep `/root/autodl-tmp/idle_shutdown.sh` available but disabled, and recreate `/etc/autodl-init`.
- During current user validation, manually start the AutoDL container before testing MuseTalk generation and keep it running.
- Do not rely on Railway automatic AutoDL `power_on` until a Pro instance with a `pro-...` UUID is available.
- Never expose `SUPABASE_SERVICE_ROLE_KEY`, `AUTODL_API_TOKEN`, or Volcengine tokens in docs, logs, or client code.
- Before testing formal generation, check:
  - `https://api.kaiqiang.ai/health`
  - `https://api.kaiqiang.ai/api/avatar/health`
  - `https://api.kaiqiang.ai/api/debug/musetalk-test`
