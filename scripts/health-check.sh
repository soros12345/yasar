#!/bin/bash
# Print the readiness picture (no secrets).
set -uo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
echo "--- liveness ---"
curl -fsS "http://127.0.0.1:${API_PORT}/health" && echo
echo "--- readiness ---"
curl -fsS "http://127.0.0.1:${API_PORT}/health/ready" && echo
echo "--- web ---"
curl -fsS -o /dev/null -w "web http_status=%{http_code}\n" "http://127.0.0.1:${WEB_PORT}/"
