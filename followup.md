# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete. Phase 1 issue #1 merged (`3dd6cf6`): User + TgLinkCode models + Alembic baseline with partial unique index for link-code activity.

Quality-gate epic #11 complete (pre-commit + pre-push + hardened CI + branch protection — `970a4c0`, `b3c3e68`).

Agent infrastructure landed: seven specialized subagents under `.claude/agents/` (#13, merged `010ba7a`) with proactive triggers and tool whitelists. This PR (#15) wires them into the issue-driven flow via `CLAUDE.md` "Agent ownership" + a delegate-vs-direct decision matrix, and adds a proactive-trigger column to the README table.

## Next

1. **Phase 1 — issue #2**: `feat(auth): register/login/refresh/me + JWT dependency`. Delegate to the `implementer` agent via the `Task` tool once this integration PR (#15) lands. Argon2 + python-jose + opaque hashed refresh tokens in DB; rotate on every refresh. ADR for refresh-token storage/rotation strategy if it deviates from the ADR-0003 auth baseline (likely needs one — call `architect` first).
2. **Phase 1 — issue #4**: auth test suite against the live Postgres CI service.
3. **Phase 1 — issue #3**: frontend Login/Register/Profile + Pinia auth store, 401 → refresh interceptor.
4. **Phase 1 — separate ticket**: Telegram link-code endpoint + profile UI button. Intentionally out of #2 to keep that PR focused.
