#!/usr/bin/env bash
set -u

HEALTH_URL="http://127.0.0.1:6006/health"
START_SCRIPT="/root/autodl-tmp/start_musetalk.sh"
LOG_FILE="/root/autodl-tmp/musetalk_watchdog.log"
LOCK_DIR="/tmp/kaiqiang_musetalk_watchdog.lock"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-60}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-180}"
OK_LOG_EVERY="${OK_LOG_EVERY:-10}"

log() {
  mkdir -p "$(dirname "$LOG_FILE")"
  printf '[%s] %s\n' "$(date -Is)" "$*" >> "$LOG_FILE"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another musetalk watchdog is already running, exiting"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

health_ok() {
  curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1
}

restart_musetalk() {
  if [ ! -f "$START_SCRIPT" ]; then
    log "health failed but start script missing: $START_SCRIPT"
    return 1
  fi

  log "health failed, running: bash $START_SCRIPT"
  bash "$START_SCRIPT" >> "$LOG_FILE" 2>&1
  local start_status=$?
  sleep 30

  if health_ok; then
    log "restart result: healthy after start_musetalk.sh status=$start_status"
  else
    log "restart result: still unhealthy after start_musetalk.sh status=$start_status"
  fi
  return "$start_status"
}

log "musetalk watchdog started health_url=$HEALTH_URL interval=${INTERVAL_SECONDS}s cooldown=${COOLDOWN_SECONDS}s"

ok_count=0
last_restart_epoch=0

while true; do
  if health_ok; then
    ok_count=$((ok_count + 1))
    if [ "$ok_count" -eq 1 ] || [ $((ok_count % OK_LOG_EVERY)) -eq 0 ]; then
      log "health ok count=$ok_count"
    fi
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  now_epoch=$(date +%s)
  since_restart=$((now_epoch - last_restart_epoch))
  if [ "$last_restart_epoch" -gt 0 ] && [ "$since_restart" -lt "$COOLDOWN_SECONDS" ]; then
    log "health failed but cooldown active ${since_restart}s < ${COOLDOWN_SECONDS}s"
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  ok_count=0
  last_restart_epoch="$now_epoch"
  restart_musetalk || true
  sleep "$INTERVAL_SECONDS"
done
