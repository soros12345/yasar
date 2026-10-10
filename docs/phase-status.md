# RevenueOS Phase Status

| Phase | Packet | Status |
|---|---|---|
| V1A-0 | Bootstrap | **PASS** (2026-10-07) — see `docs/v1a-0-acceptance-report.md` |
| V1A-1 | Multi-Tenancy Security | **PASS** (2026-10-07) — see `docs/v1a-1-acceptance-report.md` |
| V1A-2 | Financial Core | **PASS** (2026-10-07) — see `docs/v1a-2-acceptance-report.md` |
| V1A-3 | Execution Authority | **PASS** (2026-10-10) — see `docs/v1a-3-acceptance-report.md` |
| V1A-4 | Execution Adapters | **PASS** (2026-10-10) — see `docs/v1a-4-acceptance-report.md` |
| V1A-5 | Awin Publisher Connector | **SKELETON — CREDENTIAL-BLOCKED** (2026-10-10) — see `docs/v1a-5-awin-connector-skeleton.md` (fail-closed connector + credential readiness; cannot PASS until a real Awin credential is provisioned) |
| V1A-6..V1A-9, V1B-*, V1C-* | ... | NOT STARTED (directories exist as forward-compatible placeholders; runtime activation forbidden) |

## V1A-0 delivered

- Native (no-Docker) PostgreSQL 17.11 + Valkey 9.1.2 built from pinned source
- `revenueos_core` database + Alembic migration `0001_bootstrap`
  (schema_version_metadata, service_health_events, application_builds)
- FastAPI API (`/health`, `/health/live`, `/health/ready`) with structured
  config layer, JSON logging, correlation IDs
- Celery worker (EXECUTE) — Celery Beat absent and asserted absent
- APScheduler scheduler (WHEN) — single schedule authority, Valkey-locked
  dispatch, heartbeat in Valkey
- Next.js 16 web bootstrap shell (TanStack Query + next-intl + shadcn-style
  components) with API/DB/worker/scheduler status, environment and build info
- 52 tests (27 unit, 25 integration), security scans, four manifests,
  native start/stop/restart scripts

## V1A-4 delivered

- `revenueos-capabilities`: `provider_capabilities` registry + `capability_guard()`
  — a capability is usable only when registered, enabled, and VERIFIED; otherwise
  DENIED (deny-by-default, scope-enforced). Awin remains UNVERIFIED.
- `revenueos-spendguard`: `spend_guard_budgets` + `evaluate_spend()` — budget vs
  RevenueOS-recorded `provider_cost_event` spend: no budget → NOT_APPLICABLE,
  within → ALLOWED, over → DENIED; every evaluation recorded.
- `revenueos-execution-controller`: enforced guard chain (`execution_policies`
  table, deny-by-default policy, PostgreSQL advisory locks), capability-gated
  provider adapter framework (`AwinPublisherAdapter` disabled), and a
  terminal-once approval decision engine. `execute_intent()` refuses DENIED /
  APPROVAL_REQUIRED / unsatisfied-guard runs.
- Migration `0006_execution_adapters` (3 tables + approval-decision columns) and
  `/api/v1/capabilities`, `/api/v1/spend-guard/*`, `/api/v1/execution-policies`,
  `/api/v1/adapters`, plus real approve/deny decisions.
- 182 tests (103 unit + 79 integration); 19 new unit and 6 new integration tests.

## V1A-3 delivered

- `revenueos-event-backbone`: append-only `execution_events` (+ DB trigger) and a
  durable `outbox_events` queue; correlation/causation ids everywhere
- `revenueos-execution-controller`: single-audit-row Decision→…→Approval plan and
  execute-once execution; payload persisted on the run for deterministic replay
- `revenueos-workflow-state`: query-verify-retry with terminal-exactly-once states
- `revenueos-spendguard` / `capabilities` / `decision-model-adapter`: inert
  enforcement stubs — every guard state recorded `UNVERIFIED`, nothing fabricated
- Migration `0005_execution` (6 tables) + `/api/v1/execution/*` and
  `/api/v1/approval-requests/*` surfaces; Celery tasks carry correlation ids
- 157 tests (84 unit + 73 integration); 22 new unit and 13 new integration tests

## V1A-2 delivered

- `revenueos-money`: float-free exact Money + ISO 4217 exponent registry
- CanonicalFinancialLedger: accounts + append-only double-entry journal (DB triggers),
  mandatory idempotency, balanced posting with post-write re-read reconciliation
- `provider_usage_event` / `provider_cost_event` ingestion contract (RevenueOS-owned, §28)
- Migration `0003_financial_core` + `0004_ledger_purge_path_fix` (append-only purge semantics); 122 tests passing; zero test residue

## V1A-1 delivered

- `tenants`, `users`, `user_sessions`, `casbin_rule` (Alembic `0002_multitenant_security`)
- Opaque bearer sessions (SHA-256-at-rest), PBKDF2-SHA256 password hashing (stdlib, 600k iters)
- Casbin domain-scoped RBAC (TENANT_ADMIN / OPERATOR / VIEWER), PostgreSQL policy persistence
- `/api/v1/auth/login|logout|me` + tenant/user/session resources, deny-by-default on every route
- Two-tenant isolation proven: disjoint user lists, cross-tenant resource access403
- `scripts/create-tenant.sh` provisioning (password via env/stdin only, `--repair` supported)
- 91 tests (43 unit + 48 integration) passing

## Next packet (requires explicit instruction)

**V1A-5 AWIN CONNECTOR** is **CREDENTIAL-BLOCKED**: the skeleton is delivered
(`packages/affiliate`, fail-closed, `readiness: DISABLED`), but it cannot PASS
until a real Awin publisher credential is provisioned and the
`awin_publisher_redirect` capability is VERIFIED. See
`docs/v1a-5-awin-connector-skeleton.md` for exactly what is required to finish it.
