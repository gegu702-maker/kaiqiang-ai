# P2.8 Subtitle MVP Stable Report

## Goal

P2.8 adds default burned-in Chinese subtitles for newly generated Avatar Studio talking-head MP4 videos.

## Scope

- Backend generates ASS subtitles from `script_text`.
- FFmpeg burns subtitles into the final MP4 before Supabase Storage upload.
- If subtitle burn-in fails, the task falls back to the original MP4 and remains completed.
- Vercel frontend fixes `/studio/avatar` script textarea readability.
- Existing completed videos are not reprocessed.

## Key Commits

- Initial subtitle burn-in MVP: `13e60abafebd5061497a99925bc0327518a69b9b`
- Textarea readability and AAC remux fix: `adf2eff0b7728126220effff80d3bc8b845c14dc`
- FFmpeg failure diagnostics: `1a2dde7aaa49e101ad91073d287a63a952d26118`
- Railway low-resource FFmpeg fix: `1c3acd164fa39296b154253fbe0a1126a9ce9f53`

## Root Cause

Subtitle burn-in initially failed on Railway because FFmpeg libx264 processing was killed by the platform with returncode `-9`.

Confirmed working before the kill:

- `script_text` reached the subtitle path.
- ASS subtitle file was generated.
- libass loaded successfully.
- fontconfig loaded successfully.
- `Noto Sans CJK SC` was found.
- FFmpeg entered h264 to libx264 encoding.

The issue was Railway CPU/memory pressure during subtitle burn-in, not font, libass, or text routing.

## Final Fix

The FFmpeg subtitle burn-in command was reduced for Railway resource limits:

- `preset=ultrafast`
- `crf=28`
- `threads=1`
- `x264-params=rc-lookahead=0:sync-lookahead=0:ref=1:no-mbtree=1`
- AAC audio bitrate reduced to `96k`
- `-shortest` retained
- `-movflags +faststart` retained

Diagnostics remain in place:

- `subtitle_burn_success`
- `subtitle_burn_failed_diagnostic`
- `subtitle_burn_failed_fallback_original`

## Production Deployment

Railway API:

- Deployment: `06125fed-b9b7-4529-9890-529367f3a586`
- Deployed commit: `1c3acd164fa39296b154253fbe0a1126a9ce9f53`

Vercel Production:

- Deployment: `dpl_7wNnm9apCoRXrzBEMzmxsACe64tD`
- Deployed commit: `adf2eff0b7728126220effff80d3bc8b845c14dc`

## Smoke Result

Latest successful smoke task:

- task_id: `4ab62bc4-46ab-4b26-9596-657126250482`
- status: `completed`
- result_url: `https://povfvhdnrpytxbbyndit.supabase.co/storage/v1/object/public/videos/avatar-results/4ab62bc4-46ab-4b26-9596-657126250482/0ee4a8fe810940e9bb9b2aa78a323c06.mp4`
- MP4 HEAD: `200`, `video/mp4`, `2040321 bytes`
- User visually confirmed Chinese subtitles are present.
- Latest smoke did not show `subtitle_burn_failed_fallback_original`.
- Final uploaded MP4 is considered the captioned MP4.

P2.8 subtitle MVP smoke result: PASS.

## Untouched Areas

- DB modified: NO
- SQL executed: NO
- profiles.plan modified: NO
- usage_logs modified: NO
- user_quotas touched: NO
- P2.7 Viral Analyzer quota touched: NO
- billing/stripe touched: NO
- master merged: NO

