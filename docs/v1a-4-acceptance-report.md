# REVENUEOS V1A-4 ACCEPTANCE REPORT — EXECUTION ADAPTERS

Date: 2026-10-10
Prerequisite: V1A-0 = PASS, V1A-1 = PASS, V1A-2 = PASS, V1A-3 = PASS
New third-party dependencies: **NONE** (SQLAlchemy/pydantic were already pinned;
`requirements/*.lock.txt` unchanged)

## What was built

V1A-3 recorded an authority chain but did not enforce it ("the authority chain is
recorded, not enforced"). V1A-4 makes the guards real and adds the provider
adapter boundary. Everything stays deny-by-default and nothing fabricates an
ALLOW.

- **packages/capabilities — provider capability registry.** New
  `provider_capabilities` table + `capability_guard()`. A capability is usable
  only when it is registered, `enabled`, and explicitly `VERIFIED`; an unknown,
  disabled, or unverified capability is **DENIED** (never UNVERIFIED-usable).
  Scope (`units`, `max_amount`) is enforced. The Awin publisher capability stays
  UNVERIFIED. (The V1A-3 `*_stub` helpers are retained unchanged.)

- **packages/spendguard — production budget engine.** New `spend_guard_budgets`
  table + `evaluate_spend()`. It sums RevenueOS-*recorded* `provider_cost_event`
  rows for the budget period and compares against the tenant budget:
  no budget → `NOT_APPLICABLE` (recorded, never ALLOW), within budget →
  `ALLOWED`, over budget → `DENIED`. Every evaluation is persisted as a
  `spend_guard_decisions` row. (`evaluate_stub`/`allow_stub` retained.)

- **execution-controller — enforced guard chain.**
  - `execution_policies` table + `evaluate_policy()`: internal intents
    (`post_journal_entry`, `ingest_provider_event`, `outbox_flush`) are allowed
    by default; every other intent — including `invoke_adapter` — is
    **DENY-by-default** until an explicit policy grants it. A policy can also
    require approval.
  - `locks.py`: a real PostgreSQL transaction-scoped advisory lock
    (`pg_try_advisory_xact_lock`); on non-PostgreSQL engines the state is
    `NOT_APPLICABLE`, not a fabricated ALLOW.
  - `plan_execution()` now runs the real engines and derives the run status:
    any DENIED guard → `DENIED`; approval required → `APPROVAL_REQUIRED`; else
    `PLANNED`. Guard reasons are persisted in `decision_json.guard_reasons`.
  - `execute_intent()` refuses `APPROVAL_REQUIRED`/`DENIED` runs and any run with
    an unsatisfied guard (`capability`/`spend_guard`/`policy`/`lock`/`risk`).

- **execution-controller/adapters — provider adapter framework.** A
  `ProviderAdapter` boundary with a pluggable `Transport` (`LocalTransport`
  in-process, `HttpTransport` production). `invoke_adapter()` runs the
  capability gate **before** touching any transport. The reference
  `AwinPublisherAdapter` is registered **disabled**: with no VERIFIED Awin
  capability an invocation is denied before a transport is consulted. A new
  `invoke_adapter` execution intent routes through the full authority chain.

- **execution-controller/approval — approval decision engine.** `create_approval_request()`
  and `decide_approval()` are terminal-once (a second decision → 409). Approving
  a request linked to a run releases it from `APPROVAL_REQUIRED` to `PLANNED`;
  denying it sets the run `DENIED`. The V1A-3 `/approve` and `/deny` stubs are
  replaced with real, authenticated, ADMIN-gated decisions.

- **Migration `0006_execution_adapters`** — `provider_capabilities`,
  `spend_guard_budgets`, `execution_policies`, and the approval-decision columns
  (`run_id`, `decided_by`, `decided_at`, `decision_note`) with a full reverse
  `downgrade()`.

- **API surface** — `/api/v1/capabilities` (GET/POST),
  `/api/v1/spend-guard/budgets` (GET/POST), `/api/v1/spend-guard/decisions` (GET),
  `/api/v1/execution-policies` (GET/POST), `/api/v1/adapters` (GET), plus real
  `/{id}/approve` and `/{id}/deny`. Casbin objects `provider_capability`,
  `spend_guard_budget`, `execution_policy`, `provider_adapter` — ADMIN writes,
  OPERATOR/VIEWER reads.

### Defects found and fixed during acceptance

1. The first `plan_execution` rewrite produced a uniform guard-state set; two
   V1A-3 tests encoded the old "everything UNVERIFIED" contract. They were
   updated to the V1A-4 semantics (policy ALLOWED for internal intents, guards
   NOT_APPLICABLE when no authority is configured, PostgreSQL lock ALLOWED).
2. `capability_guard` originally checked verification before enablement, so a
   disabled-but-unverified capability reported the wrong reason; the guard order
   and the test were corrected so each refusal names its cause.
3. The `execute_invoke_adapter` handler wrapped an adapter denial as an
   `ExecutionError` (mapped to 409 by the route); the integration assertion was
   corrected to the route's actual, intended 409 contract.

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| MIGRATION_0006_PASS | PASS | `0006_execution_adapters` up/down; 24-table inventory; 3 new tables + 4 new columns |
| CAPABILITY_DENY_BY_DEFAULT_PASS | PASS | unregistered/disabled/unverified capability → DENIED; VERIFIED+enabled+in-scope → ALLOWED |
| ADAPTER_CAPABILITY_GATE_PASS | PASS | Awin intent → `capability_state=DENIED`, run `DENIED`, execute → 409; no transport call for a denied capability |
| ADAPTER_DISABLED_BOUNDARY_PASS | PASS | VERIFIED capability + policy ALLOW → run PLANNED; execute refused at the adapter boundary (409) |
| SPENDGUARD_BUDGET_PASS | PASS | no budget → NOT_APPLICABLE; within → ALLOWED; recorded+requested over → DENIED; tenant-scoped |
| POLICY_DENY_BY_DEFAULT_PASS | PASS | internal intents default-ALLOW; `invoke_adapter` DENIED without a policy, ALLOWED with one |
| APPROVAL_ENGINE_PASS | PASS | decision terminal-once (second → 409); approve releases the run to PLANNED, which then executes |
| EXECUTION_GATE_PASS | PASS | DENIED/APPROVAL_REQUIRED/unsatisfied-guard runs are refused with 409 |
| ROUTE_PROTECTION_MATRIX_PASS | PASS | every new `/api/v1` route rejects missing token (401); OpenAPI inventory exact |
| RBAC_AND_ISOLATION_PASS | PASS | capability/budget/policy writes ADMIN-only (viewer/operator → 403); reads viewer-allowed; tenant-scoped budgets/policies |
| UNIT_TEST_PASS | PASS | 103/103 |
| INTEGRATION_TEST_PASS | PASS | 79/79 (incl. 19 execution) — full suite **182/182** |
| DATA_HYGIENE_PASS | PASS | post-suite residue = 0 for every V1A table |
| SECURITY_SCANS_PASS | PASS | gitleaks (all commits, no leaks), trivy executed, semgrep executed |
| SERVICE_RESTART_PASS | PASS | full stop/start → WAIT_READY_OK at phase `V1A-4`, version `0.1.0+v1a4` |
| POST_RESTART_TEST_PASS | PASS | 182/182 after restart |
| NO_DOCKER_PASS | PASS | native only (unchanged) |

## Warnings / honest limitations

1. **No provider credentials.** No Awin (or other) capability is VERIFIED, so
   no external provider call can be dispatched. The adapter framework and the
   `HttpTransport` exist, but every provider path is disabled and deny-by-default.
2. **`risk_state` is NOT_APPLICABLE.** V1A-4 does not add a risk-scoring engine;
   the guard is honestly recorded as having no configured authority rather than
   fabricating an ALLOW.
3. **The advisory lock is transaction-scoped.** It serializes concurrent planning
   transactions for a tenant+intent; it is not a cross-transaction business lock.
4. **Awin connector is V1A-5** (per `provider-manifest.yaml`); V1A-4 delivers the
   framework and the disabled reference adapter only.
5. `HttpTransport` is untested against a live provider (there is none to test).

## Manifests / docs

- No new third-party repositories → `repo-manifest.yaml` unchanged except the
  phase line; `requirements/*.lock.txt` unchanged.
- `runtime-manifest.yaml`: service versions → `0.1.0+v1a4`.
- `.env` / `.env.example`: `PHASE=V1A-4`, `APP_VERSION=0.1.0+v1a4`.
- `docs/phase-status.md`: V1A-4 = PASS.

## Final status

V1A-4 = PASS — STOP IMPLEMENTATION (V1A-5 not started).
