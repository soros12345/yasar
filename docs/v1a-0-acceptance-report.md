# REVENUEOS V1A-0 ACCEPTANCE REPORT

Date: 2026-10-07
Commit: 3f927bc

Environment: native cloud VM, NO DOCKER (docker binary exists on host but is never invoked by RevenueOS)
OS: Ubuntu 24.04.5 LTS (Linux 6.1.102, x86_64)
Python: 3.12.3 (venvs: .venv-api, .venv-worker, .venv-test, .venv-tools)
Node: 24.21.0 (npm 11.19.0)
PostgreSQL: 17.11 (native source build, --without-readline --without-icu, scram-sha-256 host auth)
Valkey: 9.1.2 (native source build, jemalloc)

## Pinned dependencies (exact; lockfiles: requirements/*.lock.txt, package-lock.json)

Backend:  fastapi 0.142.2 · uvicorn 0.54.0 · SQLAlchemy 2.1.3 · pydantic 2.13.5 ·
pydantic-settings 2.15.0 · alembic 1.20.0 · httpx 0.28.1 · psycopg 3.3.6 (LGPL noted) ·
celery 5.6.3 · redis-py 8.1.0 (Valkey RESP client) · APScheduler 3.11.3 · pytest 9.1.1 · semgrep 1.179.0
Frontend: next 16.4.0 · react 19.3.0 · @tanstack/react-query 5.104.1 · next-intl 4.14.9 ·
tailwindcss 4.3.3 · class-variance-authority 0.7.1 · typescript 5.9.3
Security binaries: gitleaks 8.30.1 · trivy 0.75.0 (pinned release binaries in .runtime/bin)

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| WEB_BOOT | PASS | next build (Turbopack) + `next start` → HTTP 200 text/html, shell renders RevenueOS, `/api/health/ready` proxy returns ready:true |
| API_BOOT | PASS | uvicorn FastAPI pid-file service, `GET /health` 200 |
| POSTGRES_NATIVE | PASS | source-built postgres process (no container), cluster .runtime/pgdata |
| VALKEY_NATIVE | PASS | source-built valkey-server process (no container) |
| DB_CONNECTION | PASS | SELECT 1 probe in /health/ready + integration tests |
| ALEMBIC_MIGRATION | PASS | `upgrade head` → 0001_bootstrap (head); tables: schema_version_metadata, service_health_events, application_builds |
| CELERY_WORKER | PASS | control ping celery_nodes=1; echo_health task round-trip |
| APSCHEDULER | PASS | heartbeat job every 10s in Valkey; scheduler component "up" (age < 1s) |
| CELERY_BEAT_DISABLED | PASS | beat_schedule forced {} + no beat process + no script invokes `celery beat` (unit-tested) |
| SCHEDULE_TO_CELERY | PASS | integration test: APScheduler fires → Valkey lock → Celery task → Valkey counter == 1 |
| DUPLICATE_SCHEDULE_PREVENTION | PASS | lock (SET NX EX) blocks re-dispatch incl. simulated restart; rebuild never duplicates job config |
| UNIT_TEST | PASS | 27/27 |
| INTEGRATION_TEST | PASS | 25/25 (live postgres, valkey, api, worker, scheduler, web) |
| GITLEAKS | PASS | 2 commits scanned, no leaks found |
| TRIVY_SCAN_EXECUTED | PASS | executed; 1 HIGH finding: CVE-2023-28859 in redis 4.5.1 inside .runtime/src/valkey-9.1.2 vendored dev tooling (NOT a RevenueOS dependency; our redis-py is 8.1.0) |
| SEMGREP_SCAN_EXECUTED | PASS | executed; 151 p/python rules on 22 files → 0 findings (fallback local ruleset: scripts/semgrep-rules.yml) |
| NO_HARDCODED_SECRET | PASS | secrets only via SecretStr/.env (gitignored); gitleaks clean |
| ENV_EXAMPLE | PASS | .env.example complete, no secret values |
| MANIFESTS | PASS | repo/runtime/provider/tool manifests created |
| SERVICE_RESTART | PASS | scripts/restart-services.sh: full stop + start of all 6 services → WAIT_READY_OK |
| POST_RESTART_TEST | PASS | full suite after restart: 52/52 passed |
| NO_DOCKER | PASS | native processes only; unit test asserts no container usage in build/runtime paths |

Full suite: 52 passed (27 unit + 25 integration), 0 failed — run before restart and after restart.

## Warnings

1. Trivy HIGH CVE-2023-28859 located in the upstream Valkey source tree's bundled
   `.runtime/src/valkey-9.1.2/utils/req-res-validator/requirements.txt` (vendored dev tool,
   never installed). Not part of RevenueOS dependency closure.
2. npm 11 install-scripts policy blocked postinstall scripts for @swc/core and @parcel/watcher;
   @swc/core verified loading correctly without postinstall (native bindings ship as optional deps).
3. PostgreSQL built without OpenSSL (no headers available without root). Connections are
   loopback-only scram-sha-256. TLS for remote DB access must be added for real production.
4. Trivy/semgrep report files: .runtime/logs/trivy-report.txt, .runtime/logs/semgrep-report.txt.

## Known limitations

1. Browser-side JS hydration (live env indicator updating from UNKNOWN → development) verified
   only via HTTP/HTML/CSS/proxy checks; interactive browser confirmation pending (no browser
   automation in V1A-0).
2. systemd units are planned entries in runtime-manifest (this environment has no systemd for
   user services); scripts/*.sh are the V1A-0 control plane.
3. AWIN provider: interface directories only, capability = UNVERIFIED (V1A-5).
4. next-intl wired with fixed locale en; locale routing arrives with the website/content packet.
5. No V1A-1+ business tables, features, or helpers exist — by design (phase lock).

## Files created

  .env.example
  .gitignore
  README.md
  agents/affiliate/.gitkeep
  agents/competitive-intelligence/.gitkeep
  agents/content/.gitkeep
  agents/growth/.gitkeep
  agents/operations/.gitkeep
  agents/product-intelligence/.gitkeep
  agents/research/.gitkeep
  agents/revenue/.gitkeep
  agents/risk-compliance/.gitkeep
  apps/api/.gitkeep
  apps/api/alembic.ini
  apps/api/alembic/env.py
  apps/api/alembic/script.py.mako
  apps/api/alembic/versions/0001_bootstrap.py
  apps/api/pyproject.toml
  apps/api/src/revenueos_api/__init__.py
  apps/api/src/revenueos_api/main.py
  apps/api/src/revenueos_api/models.py
  apps/api/src/revenueos_api/routers/__init__.py
  apps/api/src/revenueos_api/routers/health.py
  apps/browser-worker/.gitkeep
  apps/scheduler/.gitkeep
  apps/scheduler/pyproject.toml
  apps/scheduler/src/revenueos_scheduler/__init__.py
  apps/scheduler/src/revenueos_scheduler/jobs.py
  apps/scheduler/src/revenueos_scheduler/main.py
  apps/web/.gitkeep
  apps/web/messages/en.json
  apps/web/next-env.d.ts
  apps/web/next.config.mjs
  apps/web/package.json
  apps/web/postcss.config.mjs
  apps/web/src/app/globals.css
  apps/web/src/app/layout.tsx
  apps/web/src/app/page.tsx
  apps/web/src/components/providers.tsx
  apps/web/src/components/shell-header.tsx
  apps/web/src/components/status-board.tsx
  apps/web/src/components/ui/badge.tsx
  apps/web/src/components/ui/button.tsx
  apps/web/src/components/ui/card.tsx
  apps/web/src/i18n/request.ts
  apps/web/src/lib/utils.ts
  apps/web/tsconfig.json
  apps/worker/.gitkeep
  apps/worker/pyproject.toml
  apps/worker/src/revenueos_worker/__init__.py
  apps/worker/src/revenueos_worker/celery_app.py
  apps/worker/src/revenueos_worker/tasks.py
  docs/.gitkeep
  infra/caddy/.gitkeep
  infra/keycloak/.gitkeep
  infra/openbao/.gitkeep
  infra/opentelemetry/.gitkeep
  infra/prometheus/.gitkeep
  infra/systemd/.gitkeep
  infra/uptime-kuma/.gitkeep
  package-lock.json
  package.json
  packages/accounting/.gitkeep
  packages/affiliate-program-change-monitor/.gitkeep
  packages/affiliate-program-lifecycle/.gitkeep
  packages/affiliate/.gitkeep
  packages/agent-evaluation/.gitkeep
  packages/agent-permissions/.gitkeep
  packages/agent-sdk/.gitkeep
  packages/agents/.gitkeep
  packages/ai-visibility/.gitkeep
  packages/allocation/.gitkeep
  packages/authorization/.gitkeep
  packages/automation-gateway/.gitkeep
  packages/backups/.gitkeep
  packages/calibration/.gitkeep
  packages/capabilities/.gitkeep
  packages/compatibility/.gitkeep
  packages/competitor-intelligence/.gitkeep
  packages/compliance/.gitkeep
  ... (219 tracked files total; forward-compatible empty module directories carry .gitkeep)

## Manifests created

repo-manifest.yaml (27 repo entries, exact pins) · runtime-manifest.yaml (6 active services + 6 future, enabled:false) ·
provider-manifest.yaml (awin + 3 placeholders, all enabled:false / UNVERIFIED) · tool-manifest.yaml
(3 installed security scanners + 9 future helpers enabled:false, authority=false)

## Final status

V1A-0 = PASS

STOP IMPLEMENTATION — V1A-1 must not begin until explicitly instructed.
