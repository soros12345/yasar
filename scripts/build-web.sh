#!/bin/bash
# Production build of the Next.js web shell.
set -euo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
cd "$WS_ROOT"
npm run build:web
echo "WEB_BUILD_OK"
