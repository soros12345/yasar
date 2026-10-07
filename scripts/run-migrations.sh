#!/bin/bash
# Alembic owns revenueos_core schema migrations.
set -euo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
cd "$WS_ROOT/apps/api"
"$VENV_API/bin/alembic" upgrade head
echo "--- alembic current ---"
"$VENV_API/bin/alembic" current
