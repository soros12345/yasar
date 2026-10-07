#!/bin/bash
# Wait until API + PostgreSQL + Valkey + worker + scheduler all report up.
set -uo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"
"$VENV_API/bin/python" - <<'PY'
import json, sys, time, urllib.request

url = "http://127.0.0.1:8000/health/ready"
deadline = time.time() + 60
last = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = json.load(resp)
        checks = {c["name"]: c["status"] for c in body.get("checks", [])}
        last = {"ready": body.get("ready"), "checks": checks}
        required = {"api": "up", "postgres": "up", "valkey": "up"}
        if body.get("ready") and all(checks.get(k) == v for k, v in required.items()) \
                and checks.get("worker") == "up" and checks.get("scheduler") == "up":
            print("WAIT_READY_OK", json.dumps(last))
            sys.exit(0)
    except Exception as exc:
        last = {"error": type(exc).__name__}
    time.sleep(1)
print("WAIT_READY_TIMEOUT", json.dumps(last))
sys.exit(1)
PY
