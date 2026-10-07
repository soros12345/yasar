#!/bin/bash
# Stop all RevenueOS native services gracefully (recorded PIDs only).
set -uo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"

descendants() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    descendants "$child"
  done
  echo "$pid"
}

stop_pidfile() {
  local name="$1" f="$PID_DIR/$1.pid" pid i
  [ -f "$f" ] || { echo "stop $name: not running"; return 0; }
  pid="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$f"; echo "stop $name: stale pid removed"; return 0
  fi
  kill -TERM "$pid" 2>/dev/null
  for i in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  for p in $(descendants "$pid"); do kill -TERM "$p" 2>/dev/null; done
  sleep 1
  for p in $(descendants "$pid"); do kill -KILL "$p" 2>/dev/null; done
  rm -f "$f"
  echo "stop $name: stopped (pid $pid)"
}

stop_pidfile web
stop_pidfile scheduler
stop_pidfile worker
stop_pidfile api

if valkey-cli -p "$VALKEY_PORT" ping >/dev/null 2>&1; then
  valkey-cli -p "$VALKEY_PORT" shutdown nosave >/dev/null 2>&1 || true
  echo "stop valkey: stopped"
else
  echo "stop valkey: not running"
fi

if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -m fast -w stop >/dev/null 2>&1 || true
  echo "stop postgres: stopped"
else
  echo "stop postgres: not running"
fi

echo "STOP_SERVICES_OK"
