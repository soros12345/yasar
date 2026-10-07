#!/bin/bash
# One-time native initialization: PostgreSQL data dir + revenueos_core DB/role.
# No Docker. Idempotent.
set -euo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"

if [ ! -f "$PGDATA/PG_VERSION" ]; then
  echo "initdb: creating PostgreSQL cluster at .runtime/pgdata"
  initdb -D "$PGDATA" --auth-local=trust --auth-host=scram-sha-256 \
    --encoding=UTF8 --locale=C >/dev/null
fi

if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -l "$LOG_DIR/postgres.log" \
    -o "-p ${POSTGRES_PORT} -k ${PGSOCK} -h 127.0.0.1" -w start >/dev/null
fi

PSQL=(psql -h "$PGSOCK" -d postgres -v ON_ERROR_STOP=1 -q)
PW="$(printf '%s' "${POSTGRES_PASSWORD:-}" | tr -d "'\"")"

exists_role=$("${PSQL[@]}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'")
if [ "$exists_role" != "1" ]; then
  "${PSQL[@]}" -c "CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${PW}'"
fi
"${PSQL[@]}" -c "ALTER ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${PW}'"

exists_db=$("${PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'")
if [ "$exists_db" != "1" ]; then
  "${PSQL[@]}" -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER}"
fi

echo "POSTGRES_INIT_OK port=${POSTGRES_PORT} db=${POSTGRES_DB} (values only, no secrets printed)"
echo "VALKEY_INIT_OK dir=.runtime/valkey-data"
