#!/bin/bash
# Restart every native service, then re-verify readiness.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/stop-services.sh"
sleep 1
"$DIR/start-services.sh"
echo "RESTART_SERVICES_OK"
