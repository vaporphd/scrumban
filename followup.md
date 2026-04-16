# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 + Phase 1 auth backend complete.

Merged to `main`:
- Phase 0 scaffold (backend + frontend + compose + CI) — `1ca2974`, `779ebe5`.
- Quality-gate epic #11 (pre-commit, pre-push, hardened CI with Postgres service, branch protection) — `970a4c0`, `b3c3e68`.
- Agent infrastructure: 7 subagent profiles in `.claude/agents/` (#13, merged `010ba7a`) + issue-driven integration rules in `CLAUDE.md` (#15, merged `eabf32a`).
- Phase 1 issue #1: `User` + `TgLinkCode` models with partial unique index for active link codes — `3dd6cf6`.
- Phase 1 issue #2: auth backend — `POST /api/auth/{register,login,refresh}`, `GET /api/me`, argon2 password hashing, HS256 JWT access tokens, opaque rotating refresh tokens (ADR-0005, migration `fcecc869fd60`) with transactional rotation and chain-revoke on replay — `ca30aaf`. Minimum-viable sanity tests (5 passing) cover register happy path, login returns pair, `/me` requires Bearer, refresh rotates + replay detection. Full auth test suite tracked in #4.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens).

Reviewer caught three should-fixes on PR #17 before merge (TTL config/ADR mismatch, too-broad `BaseException`, chain-revoke predicate wording) — all addressed in the fixup commit. Establishes that the agent cascade architect → implementer → reviewer is working end-to-end.

## Next

1. **Issue #18** — the PR you're looking at: harden the `followup.md` rule so future PRs can't silently leak cross-session memory. Promote followup update to hard-gate; reviewer must block on missing/stale Status or Next.
2. **Phase 1 — issue #3**: frontend Login / Register / Profile views + Pinia auth store + 401→refresh interceptor. Consumes the endpoints from #2. Pre-commit + pre-push already gate the Vue side via `vue-tsc` and `vitest`.
3. **Phase 1 — issue #4**: full auth test suite against the live Postgres CI service. Beyond the sanity tests: concurrent refresh races, token-expiry edges, user-not-found vs wrong-password timing parity, link-code redemption edge cases.
4. **Phase 1 — separate ticket (to be opened)**: Telegram link-code endpoint (`POST /api/me/tg-link-code`) + web UI "Link Telegram" button. Intentionally kept out of #2 and #3 to keep their PRs focused.
