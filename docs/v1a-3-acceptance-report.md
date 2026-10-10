# REVENUEOS V1A-3 ACCEPTANCE REPORT — EXECUTION AUTHORITY

Date: 2026-10-10
Prerequisite: V1A-0 = PASS, V1A-1 = PASS, V1A-2 = PASS
New third-party dependencies: **NONE** (SQLAlchemy/pydantic/redis already pinned;
`requirements/*.lock.txt` unchanged)

## What was built

- **packages/event-backbone (revenueos-event-backbone)** — append-only event log +
  durable outbox:
  - `execution_events` (id, tenant, correlation_id, causation_id, event_type,
    payload_json, occurred_at) and `outbox_events` (deterministic dispatch queue,
    `state`/`attempts`/`dispatched_at`). Both FKs cascade from `tenants`.
  - `append_event()` requires tenant + correlation + type; `enqueue_outbox()` is
    idempotent by (tenant, correlation_id, destination); `mark_outbox_dispatched()`
    is tenant-scoped, idempotent, and records a tz-aware `dispatched_at`.
  - PostgreSQL trigger `trg_execution_events_append_only` forbids UPDATE/DELETE on
    `execution_events` (operator escape hatch GUC `revenueos.allow_execution_purge`,
    same controlled-purge convention as the ledger).
- **packages/execution-controller (revenueos-execution-controller)** — the sole
  external side-effect authority. `ExecutionControllerRun` is the audit trail of
  every decision; `ApprovalRequest` is the deny-by-default approval surface.
  - `plan_execution()` runs Decision → Plan → Capability → SpendGuard → Policy →
    Locks → Risk → Approval in **one** recorded run (status `PLANNED`) and persists
    the payload on the run so execution is deterministic/replayable by correlation id.
    Every guard state is recorded as `UNVERIFIED`: no authorization is fabricated.
  - `execute_intent()` executes exactly once: it refuses unknown intents and any run
    that is not `PLANNED`, dispatches to the ledger/outbox layer (idempotency keys
    preserved), and records `SUCCEEDED`/`FAILED` + `error_detail` on the same run.
  - `verify_execution()` is the query-verify-retry boundary: it records the explicit
    verification outcome and appends `execution.verified`.
- **packages/workflow-state (revenueos-workflow-state)** — long-lived
  uncertain-result procedures with explicit terminal states. A workflow is terminal
  **exactly once**: further `record_verification`/`mark_awaiting_verification` calls
  raise `WorkflowAlreadyTerminal` (no implicit retry).
- **packages/spendguard / capabilities / decision-model-adapter** — enforcement
  **stubs**, inert by construction: no spend/capability/decision value is ever
  fabricated as ALLOWED. `evaluate_stub()` records `UNVERIFIED` (or the explicit
  `DENIED` branch) for every evaluation; `allow_stub()` is the documented test-only
  escape hatch; `is_within_scope_stub()` is deny-by-default (`False`);
  `decide_stub()` returns `UNVERIFIED` with no recommendation.
- **Migration `0005_execution`** — creates `execution_controller_runs`,
  `execution_events`, `outbox_events`, `approval_requests`, `workflow_instances`,
  `spend_guard_decisions` (6 tables, 13 new indexes), the append-only trigger, and a
  full reverse `downgrade()`. JSON payload columns are real `json` columns, matching
  the V1A-2 convention and the ORM `sa.JSON` types.
- **API surface** — `/api/v1/execution/{decide,runs,runs/{id},runs/{id}/execute,
  runs/{id}/verify,events,outbox/pending,workflows,workflows/{id}/verify}` and
  `/api/v1/approval-requests` (+ `/{id}/approve|/deny`). Casbin objects
  `execution_controller_run`, `execution_event`, `approval_request`, `outbox_event`,
  `workflow_instance`, `spend_guard_decision` — ADMIN writes, OPERATOR/VIEWER reads.
- **Celery task hardening** — every task carries a correlation id and logs it;
  `revenueos.execution.outbox_flush` is the internal execution channel task and is
  idempotent by correlation id (query-verify-retry; no blind retry, no Celery Beat).

### Defects found and fixed during acceptance

The first acceptance run of the new integration suite exposed real defects that the
existing unit tests did not cover. All were fixed at the cause (not by weakening tests):

1. `0005` created `decision_json`/`payload_json`/`subject_json` as `text` while the
   ORM declared `sa.JSON` — dict payloads were not the shape the code assumed.
   Migration + `ApprovalRequest.subject_json` model aligned to real `json` columns.
2. `mark_outbox_dispatched()` used `datetime.timezone.utc` (AttributeError on the
   datetime *class*) — fixed to `timezone.utc`.
3. `spendguard.allow_stub()` referenced an unimported `SPendGuardState_ALLOWED`
   (NameError) — fixed and now covered by a test.
4. `record_verification()` allowed overwriting a terminal workflow
   (`SUCCEEDED` → `FAILED`) — terminal-once guard added and tested.
5. The claim "immutable by DB trigger" had no trigger — the `execution_events`
   append-only trigger was added and is now tested against raw UPDATE/DELETE.
6. `decide()` created a run and the router created a second one (double audit rows,
   payload discarded so execution could not work) — replaced by `plan_execution()` /
   `execute_intent()`, which also gives execute-once semantics (409 on re-execute).
7. The execution/approval routers were written but never registered, and
   approve/deny had no authentication dependency — routers registered, approve/deny
   now require `approval_request:write` (401 without a token, 403 for read-only roles).
8. The pre-existing "spendguard deny-by-default" and "workflow retry" unit tests were
   vacuous (one raised the exception it asserted; the other encoded the terminal-state
   bug) — rewritten to test the real paths.

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| MIGRATION_0005_PASS | PASS | `0005_execution` up/down verified; 21-table inventory; 6 V1A-3 tables |
| EVENT_APPEND_ONLY_PASS | PASS | raw UPDATE/DELETE on `execution_events` → DB trigger exception; row unchanged |
| CORRELATION_CAUSATION_PASS | PASS | plan+executed events share the request correlation id; `causation_id` NULL→root correlation |
| EXECUTION_AUTHORITY_PASS | PASS | `post_journal_entry` decided → executed → real balanced journal entry + line rows in the tenant ledger |
| EXECUTE_ONCE_PASS | PASS | second execute of the same run → 409; only `PLANNED` runs execute |
| OUTBOX_PASS | PASS | enqueue idempotent by (tenant, correlation, destination); pending→dispatched with `dispatched_at`; flush never crosses tenants |
| WORKFLOW_QVR_PASS | PASS | PENDING→AWAITING→SUCCEEDED (or FAILED); terminal exactly once (re-verify → 409) |
| GUARD_STUBS_UNVERIFIED_PASS | PASS | all six guard states returned UNVERIFIED; no fabricated ALLOWED; SpendGuard decision row recorded per evaluation |
| APPROVAL_DENY_BY_DEFAULT_PASS | PASS | create is ADMIN-only (viewer/operator → 403), read viewer-allowed, approve/deny → 501 and 401 unauthenticated; request stays PENDING |
| RBAC_EXECUTION_SURFACE_PASS | PASS | viewer/operator read-only; writes → 403 |
| TENANT_ISOLATION_EXECUTION_PASS | PASS | B sees empty runs/events/outbox/approvals; A's run id → 404 for B; B cannot execute A's run |
| ROUTE_PROTECTION_MATRIX_PASS | PASS | every new `/api/v1` route rejects missing/invalid token (401); OpenAPI inventory is exact |
| UNIT_TEST_PASS | PASS | 84/84 |
| INTEGRATION_TEST_PASS | PASS | 73/73 (incl. 13 V1A-3 execution) — full suite **157/157** |
| SECURITY_SCANS_PASS | PASS | gitleaks (all commits, no leaks), trivy executed, semgrep executed |
| DATA_HYGIENE_PASS | PASS | post-suite: tenants/users/sessions/casbin/ledger/provider/execution/outbox/approval/workflow/spendguard all = 0 |
| SERVICE_RESTART_PASS | PASS | full stop/start → WAIT_READY_OK at phase `V1A-3`, version `0.1.0+v1a3` |
| POST_RESTART_TEST_PASS | PASS | 157/157 after restart |
| NO_DOCKER_PASS | PASS | native only (unchanged) |

## Warnings

1. Same single Trivy HIGH (vendored `redis` pin inside the upstream Valkey source
   tree — build-time tooling, not our dependency closure).
2. `is_within_scope_stub` is deny-by-default by returning `False` for everything;
   real capability scopes arrive with the policy packet, and no caller may treat
   `False` as an ALLOW.
3. `execution_events` immutability is enforced by trigger; `outbox_events` is
   intentionally mutable (its whole job is a state transition).

## Known limitations

1. **No approval decisions.** `/approve` and `/deny` are authenticated but return
   `501`; there is no approvals UI or decision engine in V1A-3.
2. **No real policy/SpendGuard/capability/decision engine.** They are hook-points
   that record `UNVERIFIED`; the authority chain is therefore *recorded*, not
   *enforced*. Guard `DENIED` is honoured (the SpendGuard hook raises), but nothing
   yet produces a verified ALLOW.
3. **No AWIN / provider calls.** Execution intents are limited to
   `post_journal_entry`, `ingest_provider_event`, `outbox_flush` (V1A-4+).
4. Outbox "dispatch" marks state and appends an event; actually pushing to an
   external transport is a later packet.
5. Escaping the append-only trigger requires the documented operator GUC; it is used
   only by test teardown and is never set in service code.

## Manifests / docs

- No new third-party repositories → `repo-manifest.yaml` and
  `runtime-manifest.yaml` unchanged; `requirements/*.lock.txt` unchanged.
- `.env.example` / `.env`: `PHASE=V1A-3`, `APP_VERSION=0.1.0+v1a3`.
- `docs/phase-status.md`: V1A-3 = PASS.

## Final status

V1A-3 = PASS — STOP IMPLEMENTATION (V1A-4 not started).
