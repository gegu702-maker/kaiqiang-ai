# P2.13 AutoDL / MuseTalk SOP and Watchdog Draft

## Goal

P2.13 documents the AutoDL / MuseTalk operating procedure and proposes a lightweight local watchdog. The goal is to reduce manual diagnosis when Avatar Studio generation is blocked by MuseTalk readiness issues.

This phase does not change the production website, Railway API, database, billing, quota, or MuseTalk runtime environment. The watchdog in this repository is a draft that still requires manual installation on AutoDL.

## Current Architecture

```text
Railway API -> SeetaCloud public 8443 -> AutoDL local 6006 -> MuseTalk
```

Key endpoints:

- Railway API: `https://api.kaiqiang.ai`
- Railway avatar health: `https://api.kaiqiang.ai/api/avatar/health`
- SeetaCloud public MuseTalk health: `https://u1032685-8547-93ee30c2.nmb2.seetacloud.com:8443/health`
- AutoDL local MuseTalk health: `http://127.0.0.1:6006/health`

## Service Layout

Expected AutoDL paths:

- MuseTalk root: `/root/MuseTalk`
- Service file: `/root/MuseTalk/kaiqiang_musetalk_service.py`
- Start script: `/root/autodl-tmp/start_musetalk.sh`
- Service log: `/root/autodl-tmp/musetalk_service.log`
- Start boot log: `/root/autodl-tmp/start_musetalk_boot.log`
- Optional idle shutdown script: `/root/autodl-tmp/idle_shutdown.sh`

Repo source files:

- `autodl/musetalk_service.py`
- `autodl/start_musetalk.sh`
- `autodl/idle_shutdown.sh`
- `autodl/musetalk_watchdog.sh`

The uvicorn command used by `start_musetalk.sh` is:

```bash
uvicorn kaiqiang_musetalk_service:app --host 0.0.0.0 --port 6006
```

## Three-Layer Health Checks

Run these in order when diagnosing service readiness.

AutoDL local check, run inside AutoDL:

```bash
curl -fsS http://127.0.0.1:6006/health
```

SeetaCloud public check, run from any machine:

```bash
curl -fsS https://u1032685-8547-93ee30c2.nmb2.seetacloud.com:8443/health
```

Railway check, run from any machine:

```bash
curl -fsS https://api.kaiqiang.ai/api/avatar/health
```

Expected healthy MuseTalk response:

```json
{"status":"ok","engine":"musetalk","root":"/root/MuseTalk"}
```

Expected healthy Railway response:

```json
{"status":"ok","musetalk":{"status":"ok","engine":"musetalk","root":"/root/MuseTalk"}}
```

## Manual Start SOP

Run inside AutoDL:

```bash
bash /root/autodl-tmp/start_musetalk.sh
```

Then confirm local health:

```bash
curl -fsS http://127.0.0.1:6006/health
```

If local health is OK, check the public layer:

```bash
curl -fsS https://u1032685-8547-93ee30c2.nmb2.seetacloud.com:8443/health
```

Then check Railway:

```bash
curl -fsS https://api.kaiqiang.ai/api/avatar/health
```

Useful local inspection commands:

```bash
ps aux | grep '[u]vicorn kaiqiang_musetalk_service:app'
cat /root/autodl-tmp/musetalk_service.pid
tail -100 /root/autodl-tmp/start_musetalk_boot.log
tail -100 /root/autodl-tmp/musetalk_service.log
cat /etc/autodl-init
```

## Failure Decision Table

| Symptom | Likely Cause | What To Check | Action |
| --- | --- | --- | --- |
| AutoDL cannot be reached and local commands cannot run | AutoDL is powered off | AutoDL console status | Start AutoDL manually, then run `start_musetalk.sh`. |
| AutoDL is on but `127.0.0.1:6006/health` fails | MuseTalk uvicorn process is down or unhealthy | `ps aux`, service logs, start boot log | Run `bash /root/autodl-tmp/start_musetalk.sh`. |
| Local `6006` OK but public `8443` fails or returns 404 HTML | SeetaCloud public mapping is not ready or mapped to the wrong target | Public health URL, AutoDL custom service mapping | Wait for mapping recovery or fix public mapping in AutoDL / SeetaCloud. |
| Public `8443` OK but Railway `/api/avatar/health` unhealthy | Railway cannot reach public host, DNS/TLS/network issue, or stale config | Railway avatar health JSON and configured host | Recheck public URL from a neutral network; verify Railway env if persistent. |
| Railway `/health` fails | Railway API is down | `https://api.kaiqiang.ai/health` | Investigate Railway API deployment separately. |
| Quota is normal but generation fails immediately with MuseTalk readiness error | Service readiness issue, not quota | Three-layer health checks | Restore local 6006 and public 8443, then retry only after P2.12 UI shows ready. |
| `/studio/avatar` shows service unavailable and button disabled | P2.12 frontend guard is working | Railway `/api/avatar/health` | Do not submit generation. Restore MuseTalk first. |

## Pre-Generation SOP

Before an important demo or real generation:

1. Confirm AutoDL is powered on.
2. Inside AutoDL, confirm local MuseTalk:
   ```bash
   curl -fsS http://127.0.0.1:6006/health
   ```
3. Confirm SeetaCloud public mapping:
   ```bash
   curl -fsS https://u1032685-8547-93ee30c2.nmb2.seetacloud.com:8443/health
   ```
4. Confirm Railway sees MuseTalk:
   ```bash
   curl -fsS https://api.kaiqiang.ai/api/avatar/health
   ```
5. Open `/studio/avatar` and confirm it displays:
   ```text
   数字人生成服务已就绪。
   ```
6. Only then start a real generation.

## Watchdog Design

Draft script:

- Repo path: `autodl/musetalk_watchdog.sh`
- AutoDL target path: `/root/autodl-tmp/musetalk_watchdog.sh`
- Log file: `/root/autodl-tmp/musetalk_watchdog.log`
- Boot log: `/root/autodl-tmp/musetalk_watchdog_boot.log`

The watchdog checks only local MuseTalk health:

```bash
http://127.0.0.1:6006/health
```

If local health fails, it runs:

```bash
bash /root/autodl-tmp/start_musetalk.sh
```

It intentionally does not:

- power on AutoDL
- call the AutoDL API
- check Railway
- check SeetaCloud public `8443`
- call `/generate`
- trigger GPU generation
- shut down the machine

Limitations:

- If AutoDL is powered off, the watchdog is not running and cannot help.
- If local 6006 is healthy but public 8443 mapping is broken, the watchdog will not restart anything.
- It does not replace the P2.12 frontend guard, which prevents users from submitting tasks when Railway reports MuseTalk unhealthy.

## Watchdog Start And Stop

Manual start on AutoDL:

```bash
chmod +x /root/autodl-tmp/musetalk_watchdog.sh
nohup bash /root/autodl-tmp/musetalk_watchdog.sh >> /root/autodl-tmp/musetalk_watchdog_boot.log 2>&1 &
```

Stop watchdog:

```bash
pkill -f '[m]usetalk_watchdog.sh'
```

Inspect logs:

```bash
tail -100 /root/autodl-tmp/musetalk_watchdog.log
tail -100 /root/autodl-tmp/musetalk_watchdog_boot.log
```

## /etc/autodl-init Recommendation

After manually confirming the watchdog script works on AutoDL, `/etc/autodl-init` can include:

```bash
nohup bash /root/autodl-tmp/musetalk_watchdog.sh >> /root/autodl-tmp/musetalk_watchdog_boot.log 2>&1 &
```

Do not write this remotely until the AutoDL environment has been manually verified.

Recommended `/etc/autodl-init` audit before changes:

```bash
cat /etc/autodl-init
ls -l /etc/autodl-init /root/autodl-tmp/start_musetalk.sh /root/autodl-tmp/musetalk_watchdog.sh
```

## Rollback

To roll back the watchdog:

1. Remove the watchdog startup line from `/etc/autodl-init`.
2. Stop any running watchdog:
   ```bash
   pkill -f '[m]usetalk_watchdog.sh'
   ```
3. Leave logs in place for audit:
   ```bash
   /root/autodl-tmp/musetalk_watchdog.log
   /root/autodl-tmp/musetalk_watchdog_boot.log
   ```
4. Keep `start_musetalk.sh` unchanged so manual startup remains available.

## Safety Notes

- P2.12 already prevents failed submissions when Railway reports MuseTalk unhealthy.
- Do not use `/api/debug/musetalk-test` or `/studio/avatar` generation as a health check, because those can trigger GPU work.
- Prefer `/health` endpoints for readiness checks.
- Any remote AutoDL installation must be confirmed manually before editing `/etc/autodl-init`.
