# REVENUEOS V1A-2 ACCEPTANCE REPORT — FINANCIAL CORE

Date: 2026-10-07
Prerequisite: V1A-0 = PASS, V1A-1 = PASS
New third-party dependencies: **NONE** (stdlib `decimal` only — no speculative packages)

## What was built

- **packages/money (revenueos-money)**: `Money` value object — floats rejected at
  every entry point, exact `Decimal` arithmetic, ISO 4217 exponent registry
  (explicit subset + `register_currency`; unknown currencies REJECTED, never
  guessed), ROUND_HALF_UP quantization to minor units.
- **packages/ledger (revenueos-ledger)** — CanonicalFinancialLedger:
  - `ledger_accounts` (5 kinds, normal-balance derivation, per-tenant unique codes)
  - `ledger_journal_entries` + `ledger_journal_lines` (double-entry, NUMERIC(20,6),
    amount > 0, side ∈ {DEBIT, CREDIT}, mandatory idempotency key + content fingerprint)
  - **Append-only at BOTH layers**: service exposes no update/delete paths, and
    PostgreSQL triggers forbid UPDATE/DELETE on entries/lines and DELETE on accounts
    (documented operator GUC escape hatch `revenueos.allow_ledger_purge` for
    controlled purge only).
  - `post_entry()`: validate → balanced check (exact Decimal ΣD = ΣC) → single
    transaction → **post-write re-read reconciliation** before commit.
  - Idempotency: same key + same content → reuse; same key + different content → conflict.
  - `provider_usage_event` / `provider_cost_event` (RevenueOS-owned per §28):
    ingestion contract with dedupe keys, tenant-scoped, `journal_entry_id` link
    permitted ONLY to the tenant's own actually-posted entries — no auto-derived
    or fabricated financial truth.
- **Migration `0003_financial_core`** (empty-safe, reversible) + trigger DDL,
  followed by **`0004_ledger_purge_path_fix`**: a controlled experiment during
  acceptance revealed 0003's purge path returned NULL (which CANCELS row
  operations in BEFORE triggers → silent `DELETE 0` while parent cascades
  produced orphaned rows). 0004 fixes the semantics (GUC-on returns OLD/NEW,
  GUC-off still RAISE), all orphaned test rows were purged, fixture cleanup
  bugs (casbin p-rule columns) were fixed, and a post-suite assertion now
  proves fixtures leave **zero residue**.
- **API**: `/api/v1/ledger/accounts|entries|entries/{id}|balances` and
  `/api/v1/provider-events/usage|cost` — Casbin-protected with new objects
  (`ledger_account`, `journal_entry`, `provider_event`): ADMIN writes,
  OPERATOR/VIEWER reads. Amounts are **strict decimal strings — JSON numbers
  rejected with 422** at the contract boundary.

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| MIGRATION_0003_PASS | PASS | `0003_financial_core` + `0004_ledger_purge_path_fix`; exact 13-table inventory;4 migrations linear/reversible |
| MONEY_EXACTNESS_PASS | PASS | float input rejected (unit + API 422); Decimal-only arithmetic |
| ROUNDING_RULES_PASS | PASS | USD 10.005→10.01, JPY 100.6→101, KWD 2.345 preserved, 0.001 USD→400 |
| BALANCED_ENFORCEMENT_PASS | PASS | unbalanced → 400 with zero rows persisted; ΣD=ΣC verified in-service, in-API, and in raw SQL per tenant |
| APPEND_ONLY_PASS | PASS | raw UPDATE/DELETE → DB trigger exception (GUC-off); purge path (GUC-on) verified by controlled experiment: DELETE 1 rowcounts, zero orphans |
| IDEMPOTENCY_PASS | PASS | same key+content → same entry id, no duplicates; different content → 409 |
| DB_CONSTRAINTS_PASS | PASS | CHECK/UNIQUE/FK constraints (positive amounts, sides, codes, idem keys) |
| TENANT_ISOLATION_LEDGER_PASS | PASS | B sees empty ledger; cross-tenant entry fetch → 404; foreign `journal_entry_id` link → 400; independent per-tenant accounting equation |
| PROVIDER_EVENT_CONTRACT_PASS | PASS | usage/cost ingest + dedupe; float quantity → 422; zero/negative cost → 400; no derived conversions |
| RBAC_FINANCIAL_SURFACE_PASS | PASS | viewer/operator read-only; writes → 403 |
| UNIT_TEST_PASS | PASS | 62/62 |
| INTEGRATION_TEST_PASS | PASS | 60/60 (25 V1A-0 + 23 V1A-1 + 12 V1A-2) — full suite 122/122 |
| SECURITY_SCANS_PASS | PASS | gitleaks (all commits, no leaks), trivy executed, semgrep executed |
| DATA_HYGIENE_PASS | PASS | full suite leaves tenants/users/sessions/entries/lines/accounts/events/casbin all = 0 (verified after every run) |
| SERVICE_RESTART_PASS | PASS | full stop/start → WAIT_READY_OK |
| POST_RESTART_TEST_PASS | PASS | 122/122 after restart |
| NO_DOCKER_PASS | PASS | native only (unchanged) |

## Warnings

1. Same single Trivy HIGH (vendored redis in the upstream Valkey source tree; not our dependency closure).
2. Account metadata (name/status) may be updated (CLOSED retirement); journal data never.

## Known limitations

1. Single-currency journal entries (per-entry currency); FX conversion/dual-entry
   multi-currency belongs to a future packet with explicit rounding policies.
2. Refunds/credits modeled as positive amounts with direction + cost_type; negative
   line amounts are forbidden by design (adjustment entries are the correct form).
3. `tool_usage_event` / `tool_cost_event` (§28) deferred until tool consumption exists (V1A-7).
4. Cost-event→ledger settlement is manual/link-only in V1A-2; automation requires
   ProfitBrain/policy packets (V1A-3+ authority chain).
5. Reconciliation is on-demand (balances endpoint + tests); scheduled reconciliation
   jobs arrive with the scheduler work later.

## Manifests / docs

- No new repos → `repo-manifest.yaml` unchanged (stdlib only).
- `docs/phase-status.md`: V1A-2 = PASS.

## Final status

V1A-2 = PASS — STOP IMPLEMENTATION (V1A-3 not started).
