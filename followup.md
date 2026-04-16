# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete; Phase 1 auth loop is now closed end-to-end (backend + frontend).

Merged to `main`:
- Phase 0 scaffold (backend + frontend + compose + CI) — `1ca2974`, `779ebe5`.
- Quality-gate epic #11 (pre-commit, pre-push, hardened CI with Postgres service, branch protection) — `970a4c0`, `b3c3e68`.
- Agent infrastructure: 7 subagent profiles in `.claude/agents/` (#13, merged `010ba7a`) + issue-driven integration rules in `CLAUDE.md` (#15, merged `eabf32a`).
- `followup.md` hard-gate hardening (#18, merged `7508f16`) — reviewer now blocks on missing/stale Status or Next.
- Phase 1 issue #1: `User` + `TgLinkCode` models with partial unique index for active link codes — `3dd6cf6`.
- Phase 1 issue #2: auth backend — `POST /api/auth/{register,login,refresh}`, `GET /api/me`, argon2 password hashing, HS256 JWT access tokens, opaque rotating refresh tokens (ADR-0005, migration `fcecc869fd60`) with transactional rotation and chain-revoke on replay — `ca30aaf`. Sanity tests (5 passing) cover register happy path, login returns pair, `/me` requires Bearer, refresh rotates + replay detection. Full auth test suite tracked in #4.
- Phase 1 issue #3: frontend auth — Pinia `useAuthStore` with localStorage persistence + cross-tab `storage` sync, typed `fetch` wrapper with single-flight 401→refresh retry (load-bearing against ADR-0005 chain-revoke), `Login` / `Register` / `Profile` views, router guard on `requiresAuth` / `guestOnly` routes, open-redirect-safe `?next=` handling. Bootstrap calls `/api/me` once on cold load so a page refresh keeps the session. New Vitest sanity test for the login action. End-to-end smoke against the live backend works. Squash-merged PR #21 (placeholder SHA; replace on merge).

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens).

No ADR was needed for #3: the frontend auth store, router guard, and fetch-refresh pattern are implementation details of existing decisions, not a new subsystem. One thing worth flagging as future work: the refresh token lives in `localStorage` (explicit choice per the issue) which is XSS-exfiltrable. If we decide to move to httpOnly cookies later, that's an ADR.

## Next

1. **Phase 1 — issue #4**: full auth test suite against the live Postgres CI service. Beyond the sanity tests: concurrent refresh races, token-expiry edges, user-not-found vs wrong-password timing parity, link-code redemption edge cases. Highest priority — closes the testing gap acknowledged in PR #17.
2. **Phase 1 — issue #20**: Telegram link-code endpoint (`POST /api/me/tg-link-code`) + "Link Telegram" CTA on the Profile page. `UserRead` / frontend `User` gain `tg_user_id` + `tg_username`. Carved out of #2 and #3 so their PRs stayed focused; consumed later by Phase 4's `/start <code>` bot flow.
3. **Phase 2 kickoff — to be opened**: board/column/task models + migration + repository/service skeleton. This is the entry point into Phase 2 per `tasks/todo.md`; open an issue before starting so the phase has a scope anchor. Frontend DnD is deliberately split out.
