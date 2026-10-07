#!/bin/bash
# Run the RevenueOS test suite: unit | integration | all (default).
set -euo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
mode="${1:-all}"
shift || true
cd "$WS_ROOT"
case "$mode" in
  unit) expr="unit" ;;
  integration) expr="integration" ;;
  all) expr="unit or integration" ;;
  *) echo "usage: run-tests.sh [unit|integration|all]"; exit 2 ;;
esac
exec "$VENV_TEST/bin/pytest" -m "$expr" "$@"
