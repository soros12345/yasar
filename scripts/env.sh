#!/bin/bash
# Shared native (no-Docker) environment for all RevenueOS service scripts.
# Source this file; never echo secret values from it.

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WS_ROOT
export RUNTIME_DIR="$WS_ROOT/.runtime"
export PID_DIR="$RUNTIME_DIR/pids"
export LOG_DIR="$RUNTIME_DIR/logs"
export PGDATA="$RUNTIME_DIR/pgdata"
export PGSOCK="$RUNTIME_DIR/pgsock"
export PG_BIN="$RUNTIME_DIR/pg/bin"
export VALKEY_BIN="$RUNTIME_DIR/valkey/bin"
export VALKEY_DATA="$RUNTIME_DIR/valkey-data"
export VENV_API="$WS_ROOT/.venv-api"
export VENV_WORKER="$WS_ROOT/.venv-worker"
export VENV_TEST="$WS_ROOT/.venv-test"
export PATH="$PG_BIN:$VALKEY_BIN:$PATH"

mkdir -p "$PID_DIR" "$LOG_DIR" "$PGSOCK" "$VALKEY_DATA"

if [ -f "$WS_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$WS_ROOT/.env"
  set +a
fi

export ENVIRONMENT="${ENVIRONMENT:-development}"
export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8000}"
export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-3000}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-revenueos_core}"
export POSTGRES_USER="${POSTGRES_USER:-revenueos}"
export VALKEY_PORT="${VALKEY_PORT:-6379}"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-/api}"
