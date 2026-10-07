#!/bin/bash
# Start all RevenueOS native services (no Docker). Idempotent per service.
set -uo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"

pid_alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

# --- PostgreSQL (native) ---
if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "postgres: already running"
else
  pg_ctl -D "$PGDATA" -l "$LOG_DIR/postgres.log" \
    -o "-p ${POSTGRES_PORT} -k ${PGSOCK} -h 127.0.0.1" -w start >/dev/null
  echo "postgres: started"
fi

# --- Valkey (native) ---
if valkey-cli -p "$VALKEY_PORT" ping >/dev/null 2>&1; then
  echo "valkey: already running"
else
  valkey-server --port "$VALKEY_PORT" --bind 127.0.0.1 --dir "$VALKEY_DATA" \
    --daemonize yes --pidfile "$PID_DIR/valkey.pid" --logfile "$LOG_DIR/valkey.log" \
    --save '' --appendonly no
  sleep 1
  valkey-cli -p "$VALKEY_PORT" ping >/dev/null
  echo "valkey: started"
fi

# --- API (FastAPI / uvicorn) ---
if pid_alive "$PID_DIR/api.pid"; then
  echo "api: already running"
else
  cd "$WS_ROOT"
  nohup "$VENV_API/bin/uvicorn" revenueos_api.main:app \
    --host "$API_HOST" --port "$API_PORT" \
    > "$LOG_DIR/api.log" 2>&1 &
  echo $! > "$PID_DIR/api.pid"
  echo "api: started (pid $(cat "$PID_DIR/api.pid"))"
fi

# --- Worker (Celery; NO Celery Beat anywhere) ---
if pid_alive "$PID_DIR/worker.pid"; then
  echo "worker: already running"
else
  cd "$WS_ROOT"
  nohup "$VENV_WORKER/bin/celery" -A revenueos_worker.celery_app:celery worker \
    --loglevel=INFO --concurrency=1 --hostname 'revenueos-worker@%h' \
    > "$LOG_DIR/worker.log" 2>&1 &
  echo $! > "$PID_DIR/worker.pid"
  echo "worker: started (pid $(cat "$PID_DIR/worker.pid"))"
fi

# --- Scheduler (APScheduler = single schedule authority) ---
if pid_alive "$PID_DIR/scheduler.pid"; then
  echo "scheduler: already running"
else
  cd "$WS_ROOT"
  nohup "$VENV_WORKER/bin/python" -m revenueos_scheduler.main \
    > "$LOG_DIR/scheduler.log" 2>&1 &
  echo $! > "$PID_DIR/scheduler.pid"
  echo "scheduler: started (pid $(cat "$PID_DIR/scheduler.pid"))"
fi

# --- Web (Next.js) ---
if pid_alive "$PID_DIR/web.pid"; then
  echo "web: already running"
else
  if [ ! -d "$WS_ROOT/apps/web/.next" ]; then
    echo "web: no build found, building first..."
    "$WS_ROOT/scripts/build-web.sh" || exit 1
  fi
  cd "$WS_ROOT/apps/web"
  nohup "$WS_ROOT/node_modules/.bin/next" start -H "$WEB_HOST" -p "$WEB_PORT" \
    > "$LOG_DIR/web.log" 2>&1 &
  echo $! > "$PID_DIR/web.pid"
  echo "web: started (pid $(cat "$PID_DIR/web.pid"))"
fi

echo "--- waiting for full readiness (api, postgres, valkey, worker, scheduler) ---"
exec "$WS_ROOT/scripts/wait-ready.sh"
