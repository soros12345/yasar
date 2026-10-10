# REVENUEOS V1A-5 — AWIN PUBLISHER CONNECTOR (SKELETON, CREDENTIAL-BLOCKED)

Date: 2026-10-10
Status: **SKELETON — not an acceptance gate.** V1A-5 cannot PASS until an Awin
publisher credential is provisioned and the Awin capability is VERIFIED.
Phase/version stay **V1A-4 / `0.1.0+v1a4`**; this is deliberately not claimed
as a delivered packet.

## Why it is blocked

`provider-manifest.yaml` still records:

```yaml
provider_id: awin
credential_type: UNKNOWN (publisher API credential — not yet provisioned)
verification_state: UNVERIFIED
enabled: false
```

The real Awin publisher API contract (base URL, endpoints, auth scheme) is
UNKNOWN. Inventing any of it would violate the project rule that unknown
information stays `UNKNOWN`.

## What was delivered anyway (fail-closed)

- **`packages/affiliate` (`revenueos-affiliate`)** — a new package that resolves
  Awin readiness **by reference only**:
  - `config.py` — `load_awin_config()` reads the *names* `AWIN_API_BASE_URL`
    and `AWIN_API_TOKEN` and records presence. The credential **value is never
    read into, returned by, or printed from** the config object.
  - `connector.py` — `AwinPublisherConnector` implements an explicit refusal
    ladder and **assumes no endpoint paths**; the caller supplies the path:
    `DISABLED` → `NOT_CONFIGURED` → `CONFIGURED_UNVERIFIED` → `VERIFIED`.
- **Adapter wiring** — `AwinPublisherAdapter.readiness()` delegates to the
  connector, and `/api/v1/adapters` now returns a `readiness` field so the
  deny-by-default state is visible through the API rather than implied.
- `HttpTransport` exists but is unreachable: dispatch refuses before any
  transport call when the ladder is not satisfied.

## Verification

| Check | Result |
|---|---|
| UNIT_TEST_PASS | PASS — 193/193 full suite (114 unit + 79 integration); 11 new connector tests |
| NO_SECRET_LEAK_PASS | PASS — credential value absent from the config object's repr/str/values |
| FAIL_CLOSED_PASS | PASS — each refusal level raises before any transport call (`transport.calls == []`) |
| ADAPTER_READINESS_PASS | PASS — live `/api/v1/adapters` reports `readiness: "DISABLED"` for Awin |
| POST_RESTART_TEST_PASS | PASS — 193/193 after full restart at phase `V1A-4` |

## To finish V1A-5

1. Provision an Awin publisher API credential (`AWIN_API_TOKEN`) and its base
   URL (`AWIN_API_BASE_URL`) through the operator secret store.
2. Record the real endpoint contract and auth scheme here; add path handling to
   `AwinPublisherConnector` (no guessed paths).
3. Have an operator mark the `awin_publisher_redirect` capability `VERIFIED` and
   enable the adapter; then `readiness()` returns `VERIFIED` and the V1A-4
   authority chain dispatches through `HttpTransport`.
