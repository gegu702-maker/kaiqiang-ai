#!/usr/bin/env bash
set -euo pipefail

IDLE_MINUTES="${GPU_IDLE_SHUTDOWN_MINUTES:-10}"
CHECK_SECONDS="${GPU_IDLE_CHECK_SECONDS:-60}"
THRESHOLD_SECONDS=$((IDLE_MINUTES * 60))
LOG=/root/autodl-tmp/idle_shutdown.log

activity_epoch() {
  local latest=0
  local candidate
  for path in \
    /root/autodl-tmp/musetalk_service.log \
    /root/autodl-tmp/results \
    /root/autodl-tmp/avatar_inputs \
    /root/MuseTalk/results/api; do
    if [ -e "$path" ]; then
      candidate=$(stat -c %Y "$path" 2>/dev/null || echo 0)
      if [ "$candidate" -gt "$latest" ]; then
        latest="$candidate"
      fi
    fi
  done
  echo "$latest"
}

mkdir -p /root/autodl-tmp
echo "[$(date -Is)] idle watchdog started, threshold=${THRESHOLD_SECONDS}s" >> "$LOG"

while true; do
  if pgrep -f "scripts.inference|python.*scripts.inference" >/dev/null 2>&1; then
    echo "[$(date -Is)] inference active, skip shutdown check" >> "$LOG"
    sleep "$CHECK_SECONDS"
    continue
  fi

  latest=$(activity_epoch)
  now=$(date +%s)
  idle_for=$((now - latest))

  if [ "$latest" -gt 0 ] && [ "$idle_for" -ge "$THRESHOLD_SECONDS" ]; then
    echo "[$(date -Is)] idle ${idle_for}s >= ${THRESHOLD_SECONDS}s, powering off AutoDL" >> "$LOG"
    sync || true
    /usr/sbin/poweroff || /usr/bin/shutdown -h now
    exit 0
  fi

  echo "[$(date -Is)] idle ${idle_for}s < ${THRESHOLD_SECONDS}s" >> "$LOG"
  sleep "$CHECK_SECONDS"
done
