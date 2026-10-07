# REVENUEOS V1A-1 ACCEPTANCE REPORT — MULTI-TENANT SECURITY

Date: 2026-10-07
Commit: (see git log — "V1A-1 multi-tenant security")
Prerequisite: V1A-0 = PASS

## What was built

- **Migration** `0002_multitenant_security` (empty-safe, reversible):
  `tenants`, `users`, `user_sessions`, `casbin_rule` — no business tables.
- **packages/identity**: tenants/users/sessions, PBKDF2-HMAC-SHA256 (stdlib,
  600k iterations, per-user salt, format-tagged for future migration),
  opaque 256-bit bearer tokens stored ONLY as SHA-256 hashes, expiry+revocation.
- **packages/authorization**: Casbin (pycasbin 1.43.0, Apache-2.0) with a
  RevenueOS-owned model (`r/p/g/e/m`, domain = tenant id), a RevenueOS-owned
  PostgreSQL adapter (implements `casbin.persist.Adapter`), deny-by-default
  policy content, per-decision enforcement (correctness first; no policy cache).
- **Roles**: TENANT_ADMIN (`*`/`*` in own domain), OPERATOR (user/tenant/session
  read), VIEWER (user/tenant read). Unknown objects deny for non-admin roles.
- **API**: `POST /api/v1/auth/login` (only unauthenticated business route),
  `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`,
  `GET /api/v1/tenant`, `GET /api/v1/tenants/{id}`, `GET|POST /api/v1/users`,
  `GET /api/v1/sessions` — every one behind authentication + Casbin.
- **Authority order implemented**: authenticate (401) → account/tenant security
  status (403) → Casbin business authorization (403) → tenant-scoped data access.
- **Provisioning**: `scripts/create-tenant.sh` (+ `--repair`), password via
  env/stdin only — never argv, never logged.

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| MIGRATION_0002_PASS | PASS | alembic head = `0002_multitenant_security`; exact 8-table schema inventory asserted |
| AUTH_REQUIRED_PASS | PASS | all 7 `/api/v1` routes reject missing AND invalid tokens with 401 (probe matrix) |
| LOGIN_SESSION_LOGOUT_PASS | PASS | login→me→logout→me(401); expired session 401; token stored as SHA-256 only |
| CASBIN_AUTHZ_PASS | PASS | viewer/operator denied `user:write`; viewer denied `session:read`; matrix on /me |
| TENANT_ISOLATION_PASS | PASS | two tenants: disjoint user lists; cross-tenant resource GET → 403 both directions; sessions list tenant-scoped |
| SECURITY_STATUS_GATES_PASS | PASS | suspended tenant → 403 (existing session AND new login); disabled user → 403 |
| NO_ROUTE_UNPROTECTED_PASS | PASS | exact OpenAPI path inventory + per-route 401 probe table |
| NO_CREDENTIALS_IN_LOGS_PASS | PASS | token & password absent from api.log tail; login_succeeded logged with IDs only |
| NO_SECRETS_IN_REPO_PASS | PASS | gitleaks: 4 commits, no leaks; passwords only SecretStr/env |
| UNIT_TEST_PASS | PASS | 43/43 |
| INTEGRATION_TEST_PASS | PASS | 48/48 (25 carried from V1A-0 + 23 new) — full suite 91/91 |
| SECURITY_SCANS_PASS | PASS | GITLEAKS=PASS, TRIVY=EXECUTED (known finding unchanged, see below), SEMGREP=EXECUTED (151 rules, 37 files, 0 findings) |
| PROVISIONING_SCRIPT_PASS | PASS | create → repair → duplicate-guard verified live |
| SERVICE_RESTART_PASS | PASS | full stop/start → WAIT_READY_OK |
| POST_RESTART_TEST_PASS | PASS | 91/91 after restart |
| NO_DOCKER_PASS | PASS | native processes only (unchanged) |

Full suite: **91 passed** before restart and **91 passed** after restart.

## Warnings

1. Trivy HIGH CVE-2023-28859 remains the same single finding inside
   `.runtime/src/valkey-9.1.2/utils/req-res-validator/requirements.txt`
   (upstream vendored dev tool; not a RevenueOS dependency).
2. Services were once found killed externally (no reboot, no shutdown logs —
   shared-VM process cleanup suspected); `scripts/start-services.sh` recovered
   the full stack cleanly. There is no process supervisor yet (systemd arrives
   with production infra, V1C).
3. First unknown-user login pays a one-time dummy PBKDF2 cost (anti-enumeration).

## Known limitations

1. Authentication is RevenueOS-native; Keycloak becomes the production identity
   default in V1C-6 (Casbin keeps authorization either way).
2. Users belong to exactly one tenant (multi-membership = future ADR).
3. No failed-login throttling/rate limiting yet (backlog; web proxy + logs today).
4. Enforcer loads policies from PostgreSQL per decision — correctness-first;
   a policy cache with invalidation belongs to a performance packet.
5. No login UI in the web shell yet (API-level auth is the V1A-1 surface).
6. Password hashing is PBKDF2 (stdlib, no new crypto dependency); Argon2id
   would need an ADR + dependency vetting.

## Manifests / lockfiles updated

- `repo-manifest.yaml`: pycasbin 1.43.0 marked INSTALLED (pinned, Apache-2.0, reviewed)
- `requirements/{api,test}.lock.txt`: regenerated (casbin==1.43.0)
- `.env.example`: `SESSION_TTL_HOURS`, `PBKDF2_ITERATIONS`
- `docs/phase-status.md`: V1A-1 = PASS

## Final status

V1A-1 = PASS — STOP IMPLEMENTATION (V1A-2 not started).
