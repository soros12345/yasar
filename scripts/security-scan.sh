#!/bin/bash
# V1A-0 security baseline:
#   gitleaks must PASS (zero findings), trivy and semgrep must EXECUTE.
# Findings from trivy/semgrep are reported as warnings for review.
set -uo pipefail
# shellcheck source=scripts/env.sh
. "$(dirname "$0")/env.sh"

TOOLS="$RUNTIME_DIR/bin"
LOGS="$RUNTIME_DIR/logs"
mkdir -p "$LOGS"

GITLEAKS_RC=0 TRIVY_RC=0 SEMGREP_RC=0

echo "=== gitleaks (secret scan) ==="
if [ -x "$TOOLS/gitleaks" ]; then
  if "$TOOLS/gitleaks" git --help >/dev/null 2>&1; then
    GL_CMD=(git --redact --report-format json --report-path "$LOGS/gitleaks-report.json")
  else
    GL_CMD=(detect --redact --report-format json --report-path "$LOGS/gitleaks-report.json")
  fi
  "$TOOLS/gitleaks" "${GL_CMD[@]}" "$WS_ROOT" || GITLEAKS_RC=$?
  if [ "$GITLEAKS_RC" -eq 0 ]; then echo "GITLEAKS_PASS"; else echo "GITLEAKS_FAIL rc=$GITLEAKS_RC"; fi
else
  echo "GITLEAKS_FAIL (binary missing)"; GITLEAKS_RC=99
fi

echo "=== trivy (filesystem/vulnerability scan) ==="
if [ -x "$TOOLS/trivy" ]; then
  "$TOOLS/trivy" fs --scanners vuln,secret,config --severity HIGH,CRITICAL \
    --exit-code 0 --format table "$WS_ROOT" > "$LOGS/trivy-report.txt" 2>&1 || TRIVY_RC=$?
  if [ "$TRIVY_RC" -ne 0 ]; then
    # DB pull may be blocked; retry with scanners that need no DB (still executes a scan)
    "$TOOLS/trivy" fs --scanners secret,config --exit-code 0 --format table "$WS_ROOT" \
      > "$LOGS/trivy-report.txt" 2>&1 || TRIVY_RC=$?
    [ "$TRIVY_RC" -eq 0 ] && echo "TRIVY_SCAN_EXECUTED (vuln-DB unavailable; secret+config scanners used)"
  else
    echo "TRIVY_SCAN_EXECUTED"
  fi
  tail -12 "$LOGS/trivy-report.txt" 2>/dev/null || true
else
  echo "TRIVY_SCAN_FAILED (binary missing)"; TRIVY_RC=99
fi

echo "=== semgrep (static analysis) ==="
if [ -x "$VENV_TEST/bin/semgrep" ] || [ -x "$WS_ROOT/.venv-tools/bin/semgrep" ]; then
  SEMGREP_BIN="$WS_ROOT/.venv-tools/bin/semgrep"
  [ -x "$SEMGREP_BIN" ] || SEMGREP_BIN="$VENV_TEST/bin/semgrep"
  if "$SEMGREP_BIN" scan --metrics=off --config "p/python" --quiet "$WS_ROOT" \
      > "$LOGS/semgrep-report.txt" 2>&1; then
    SEMGREP_RC=0
  else
    SEMGREP_RC=$?
    # registry may be unreachable: fall back to local rules (scan still executes)
    "$SEMGREP_BIN" scan --metrics=off --config "$WS_ROOT/scripts/semgrep-rules.yml" --quiet "$WS_ROOT" \
      > "$LOGS/semgrep-report.txt" 2>&1 || SEMGREP_RC=$?
  fi
  [ "$SEMGREP_RC" -eq 0 ] && echo "SEMGREP_SCAN_EXECUTED" || echo "SEMGREP_SCAN_FAILED rc=$SEMGREP_RC"
  grep -E "^\s*(Codemirror rules)?[0-9]+ findings?" "$LOGS/semgrep-report.txt" 2>/dev/null | tail -3 || true
else
  echo "SEMGREP_SCAN_FAILED (not installed)"; SEMGREP_RC=99
fi

echo "=== security scan summary ==="
echo "GITLEAKS=$([ "$GITLEAKS_RC" -eq 0 ] && echo PASS || echo FAIL)"
echo "TRIVY=$([ "$TRIVY_RC" -eq 0 ] && echo EXECUTED || echo FAILED)"
echo "SEMGREP=$([ "$SEMGREP_RC" -eq 0 ] && echo EXECUTED || echo FAILED)"

if [ "$GITLEAKS_RC" -ne 0 ] || [ "$TRIVY_RC" -ne 0 ] || [ "$SEMGREP_RC" -ne 0 ]; then
  exit 1
fi
echo "SECURITY_SCANS_OK"
