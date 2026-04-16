# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete; Phase 1 auth loop is now closed end-to-end (backend + frontend) and fully tested. Developer-experience tooling now includes a real-browser e2e smoke layer **and** an autonomous pre-merge review loop that runs implementer ↔ reviewer without prompting the user between steps.

Merged to `main`:
- Phase 0 scaffold (backend + frontend + compose + CI) — `1ca2974`, `779ebe5`.
- Quality-gate epic #11 (pre-commit, pre-push, hardened CI with Postgres service, branch protection) — `970a4c0`, `b3c3e68`.
- Agent infrastructure: 7 subagent profiles in `.claude/agents/` (#13, merged `010ba7a`) + issue-driven integration rules in `CLAUDE.md` (#15, merged `eabf32a`).
- `followup.md` hard-gate hardening (#18, merged `7508f16`) — reviewer now blocks on missing/stale Status or Next.
- Phase 1 issue #1: `User` + `TgLinkCode` models with partial unique index for active link codes — `3dd6cf6`.
- Phase 1 issue #2: auth backend — `POST /api/auth/{register,login,refresh}`, `GET /api/me`, argon2 password hashing, HS256 JWT access tokens, opaque rotating refresh tokens (ADR-0005, migration `fcecc869fd60`) with transactional rotation and chain-revoke on replay — `ca30aaf`. Shipped with a 5-test sanity subset — superseded by #4's full suite below.
- Phase 1 issue #3: frontend auth — Pinia `useAuthStore` with localStorage persistence + cross-tab `storage` sync, typed `fetch` wrapper with single-flight 401→refresh retry (load-bearing against ADR-0005 chain-revoke), `Login` / `Register` / `Profile` views, router guard on `requiresAuth` / `guestOnly` routes, open-redirect-safe `?next=` handling. Bootstrap calls `/api/me` once on cold load so a page refresh keeps the session. Shipped via PR #21.
- Phase 1 issue #4: full auth test suite — 17 backend tests, **99% line coverage on `app/services/auth_service.py`** (gate ≥ 90% via `--cov-fail-under` in CI). Beyond the sanity subset: wrong-password vs unknown-user 401 + response parity, register-409 (both pre-check and `IntegrityError` race), forged-token expiry + bad-signature + non-integer-`sub` + unknown-user 401s, refresh-with-garbage 401, expired refresh row 401, and a concurrent refresh race that observes the ADR-0005 outcome (1×200 + 1×401). New `client` and `auth_pair` fixtures in `conftest.py`.
- DX issue #24: `smoke-tester` subagent + Playwright e2e baseline. Runs after `implementer` and before `reviewer` on any PR that touches `frontend/`; on a failing scenario captures screenshots/video/trace under `frontend/tests/e2e/artifacts/`, retries once after `docker compose down/up`, and on a reproduced fail files an issue + delegates to `bug-hunter`. `@playwright/test@1.59.1`. 5 baseline specs cover the Phase 1 auth surface.
- DX issue #29: autonomous pre-merge review loop. `CLAUDE.md` gains a "Pre-merge review loop" subsection codifying that the main session never asks "should I run reviewer?" or "should I send these back to implementer?" — the answers are always yes. The user is asked only for (a) the rare nits-only judgment call (`approve-with-suggestions`) and (b) the final merge authorization (`approve`). `reviewer.md` now MUSTs an `gh issue comment` on must-fix/changes-requested so findings survive PR squash, and emits an explicit `## Handoff` block. `implementer.md` gains a "Re-engagement after reviewer feedback" section + matching Handoff block. Together: one routine question per PR (the merge), down from three.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens).

**In flight (open PR pending merge)**: PR #28 closes #23 — `fix(auth): close username-enumeration timing leak in authenticate()` via a precomputed `_DUMMY_PASSWORD_HASH` + dummy `verify_password` on the user-not-found branch. Before/after timing: 7.74× → 1.02× delta. Strict timing-parity assertion reinstated in `test_login_response_parity_wrong_vs_unknown` (N=10 samples, median, 30% tolerance). 17 tests pass at 99% coverage. Awaiting reviewer + merge auth.

**Known infra bug surfaced by #24**: compose `frontend` service can't reach `api` because `vite.config.ts` proxies `/api` to `http://localhost:8000` (the container itself, not the host). Workaround: run `npm run dev` on the host. Tracked as #25.

## Next

1. **Phase 1 — issue #20**: Telegram link-code endpoint (`POST /api/me/tg-link-code`) + "Link Telegram" CTA on the Profile page. `UserRead` / frontend `User` gain `tg_user_id` + `tg_username`. Carved out of #2 and #3 so their PRs stayed focused; consumed later by Phase 4's `/start <code>` bot flow. Highest priority — last open Phase 1 issue, and the smoke-tester agent now exists to lock the new Profile CTA with a `link-telegram.spec.ts`. With #29 merged, the implementer→smoke-tester→reviewer loop runs without prompting.
2. **Compose-aware vite proxy — issue #25**: `chore(infra): make vite dev proxy compose-aware`. Promote the current host-only workaround into a real fix: env-driven `VITE_API_PROXY_TARGET`, defaulting to `http://api:8000` in compose and `http://localhost:8000` on host. Removes the README/agent caveat and lets `docker compose up frontend` actually work. Cheap, unblocks #26.
3. **Playwright in CI — issue #26**: `chore(ci): run playwright e2e in CI`. Wire `npm run e2e` into a CI job so PRs opened outside the agent flow still get smoke coverage. Depends on #25 (or runs vite directly on the runner without compose). Required before flipping the e2e job into branch-protection required checks.
4. **Phase 2 kickoff — to be opened**: board/column/task/label models + Alembic migration + repository/service skeleton (no endpoints yet). Entry point into Phase 2 per `tasks/todo.md`. Open the issue first so the phase has a scope anchor; endpoints (`/api/boards`, `/api/boards/{id}/columns`, etc.) and frontend DnD split into follow-up issues.
