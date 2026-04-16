# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete; Phase 1 auth loop is now closed end-to-end (backend + frontend) and fully tested.

Merged to `main`:
- Phase 0 scaffold (backend + frontend + compose + CI) — `1ca2974`, `779ebe5`.
- Quality-gate epic #11 (pre-commit, pre-push, hardened CI with Postgres service, branch protection) — `970a4c0`, `b3c3e68`.
- Agent infrastructure: 7 subagent profiles in `.claude/agents/` (#13, merged `010ba7a`) + issue-driven integration rules in `CLAUDE.md` (#15, merged `eabf32a`).
- `followup.md` hard-gate hardening (#18, merged `7508f16`) — reviewer now blocks on missing/stale Status or Next.
- Phase 1 issue #1: `User` + `TgLinkCode` models with partial unique index for active link codes — `3dd6cf6`.
- Phase 1 issue #2: auth backend — `POST /api/auth/{register,login,refresh}`, `GET /api/me`, argon2 password hashing, HS256 JWT access tokens, opaque rotating refresh tokens (ADR-0005, migration `fcecc869fd60`) with transactional rotation and chain-revoke on replay — `ca30aaf`. Sanity tests (5 passing) cover register happy path, login returns pair, `/me` requires Bearer, refresh rotates + replay detection.
- Phase 1 issue #3: frontend auth — Pinia `useAuthStore` with localStorage persistence + cross-tab `storage` sync, typed `fetch` wrapper with single-flight 401→refresh retry (load-bearing against ADR-0005 chain-revoke), `Login` / `Register` / `Profile` views, router guard on `requiresAuth` / `guestOnly` routes, open-redirect-safe `?next=` handling. Bootstrap calls `/api/me` once on cold load so a page refresh keeps the session. New Vitest sanity test for the login action. End-to-end smoke against the live backend works. Shipped via PR #21.
- Phase 1 issue #4: full auth test suite — 17 backend tests against the live Postgres CI service, **99% line coverage on `app/services/auth_service.py`** (gate set to ≥ 90% via `--cov-fail-under` in CI). Beyond the sanity subset: wrong-password vs unknown-user 401 + response parity, register-409 (both pre-check and `IntegrityError` race branch), forged-token expiry + bad-signature + non-integer-`sub` + unknown-user 401s, refresh-with-garbage 401, expired refresh row 401, and a concurrent refresh race that locks in the ADR-0005 transactional rotation (exactly one winner, at most one live row left). New `client` and `auth_pair` fixtures in `conftest.py` so future tests do not repeat the register+login dance. CI workflow now installs `pytest-cov` and runs `pytest --cov=app.services.auth_service --cov-fail-under=90`.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens).

No ADR was needed for #4: tests are not a new subsystem.

**Known auth bug surfaced by #4 — to be filed as its own ticket before #20 lands**: `auth_service.authenticate` short-circuits when `get_by_username` returns `None`, skipping argon2 verify. Local measurements show wrong-password ≈ 29 ms vs unknown-user ≈ 4.5 ms — a ~6× timing side-channel that lets an attacker probe usernames. The strict timing-parity assertion is deliberately deferred from `test_login_response_parity_wrong_vs_unknown` until the service runs a dummy argon2 hash on the user-not-found branch. Open as `fix(auth): close username-enumeration timing leak in authenticate()` and link to PR #4.

## Next

1. **Phase 1 — issue #20**: Telegram link-code endpoint (`POST /api/me/tg-link-code`) + "Link Telegram" CTA on the Profile page. `UserRead` / frontend `User` gain `tg_user_id` + `tg_username`. Carved out of #2 and #3 so their PRs stayed focused; consumed later by Phase 4's `/start <code>` bot flow. Highest priority — it is the only other open Phase 1 issue.
2. **Phase 2 kickoff — to be opened**: board/column/task/label models + Alembic migration + repository/service skeleton (no endpoints yet). This is the entry point into Phase 2 per `tasks/todo.md`; open an issue before starting so the phase has a scope anchor. Endpoints (`/api/boards`, `/api/boards/{id}/columns`, etc.) and frontend DnD are deliberately split into follow-up issues.
3. **Auth timing side-channel — to be opened** (see Status above): `fix(auth): close username-enumeration timing leak in authenticate()`. Run a dummy argon2 verify against a constant hash on the user-not-found branch so wrong-password and unknown-user paths take comparable time. Once landed, reinstate the strict timing-parity assertion in `test_login_response_parity_wrong_vs_unknown` (currently a response-shape-only check). Small, well-bounded fix; should land before Phase 2 picks up steam so we are not stacking work on a known auth bug.
