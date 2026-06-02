#!/usr/bin/env bash
set -euo pipefail

LOG=/root/autodl-tmp/musetalk_service.log
BOOT_LOG=/root/autodl-tmp/start_musetalk_boot.log
ROOT=/root/MuseTalk
SERVICE=/root/MuseTalk/kaiqiang_musetalk_service.py
WATCHDOG=/root/autodl-tmp/idle_shutdown.sh

start_idle_watchdog() {
  if [ -x "$WATCHDOG" ]; then
    pkill -f '[i]dle_shutdown.sh' 2>/dev/null || true
    nohup "$WATCHDOG" >/root/autodl-tmp/idle_shutdown.out 2>&1 < /dev/null &
    echo "[$(date -Is)] idle watchdog pid $!"
  fi
}

mkdir -p /root/autodl-tmp /root/autodl-tmp/results /root/autodl-tmp/avatar_inputs
{
  echo "[$(date -Is)] start_musetalk invoked"

  if curl -fsS --max-time 5 http://127.0.0.1:6006/health >/dev/null 2>&1; then
    echo "[$(date -Is)] musetalk already healthy"
    start_idle_watchdog
    exit 0
  fi

  if [ ! -f "$SERVICE" ]; then
    echo "[$(date -Is)] missing service file: $SERVICE"
    exit 1
  fi

  cd "$ROOT"
  source /root/miniconda3/etc/profile.d/conda.sh
  conda activate musetalk

  pkill -f 'uvicorn kaiqiang_musetalk_service:app' 2>/dev/null || true
  sleep 2

  nohup uvicorn kaiqiang_musetalk_service:app --host 0.0.0.0 --port 6006 > "$LOG" 2>&1 < /dev/null &
  echo $! > /root/autodl-tmp/musetalk_service.pid
  echo "[$(date -Is)] started pid $(cat /root/autodl-tmp/musetalk_service.pid)"

  for i in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1:6006/health >/dev/null 2>&1; then
      echo "[$(date -Is)] musetalk healthy after ${i}s"
      start_idle_watchdog
      exit 0
    fi
    sleep 1
  done

  echo "[$(date -Is)] musetalk failed to become healthy"
  tail -80 "$LOG" || true
  exit 1
} >> "$BOOT_LOG" 2>&1
