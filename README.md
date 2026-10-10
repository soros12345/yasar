# RevenueOS / AffiliateOS

Global, multi-tenant, AI-assisted revenue operating system.

Phase status: **V1A-4 EXECUTION ADAPTERS** (see `docs/phase-status.md`).

## Layout

- `apps/` — web (Next.js), api (FastAPI), worker (Celery), scheduler (APScheduler), browser-worker (disabled until V1A-4+)
- `packages/` — shared Python packages (`shared`, `schemas`) + forward-compatible module directories (disabled)
- `plugins/`, `agents/`, `infra/` — forward-compatible directories (disabled)
- `requirements/` — pinned Python lockfiles
- `repo-manifest.yaml`, `runtime-manifest.yaml`, `provider-manifest.yaml`, `tool-manifest.yaml` — four manifests
- `scripts/` — native (no-Docker) start/stop/restart, migrations, tests, security scans

## Rules of the build

No Docker. No fabricated data. APScheduler is the single schedule authority (Celery Beat disabled).
Unknown information stays `UNKNOWN`.
