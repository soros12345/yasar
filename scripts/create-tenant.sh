#!/bin/bash
# Provision a tenant + admin using the API venv (password via env/stdin only).
set -euo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
exec "$VENV_API/bin/python" "$WS_ROOT/scripts/create-tenant.py" "$@"
