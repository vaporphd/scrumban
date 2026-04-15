# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete. Issue #1 merged (`3dd6cf6`): User + TgLinkCode models + Alembic baseline with partial unique index for link-code activity.

Quality-gate epic just opened (#11) with five subtasks (#6–#10). Implementing now, before Phase 1 auth endpoints — so the flow enforces lint-before-commit and tests-before-push for all remaining work.

Docker compose stack has been started locally: postgres-16 container up with migration applied.

## Next

1. **Issue #6** — extend `.pre-commit-config.yaml` (ruff already there; add mypy + vue-tsc).
2. **Issue #7** — add pre-push hooks (pytest + vitest).
3. **Issue #8** — harden CI: Postgres service, split steps, cache check.
4. **Issue #10** — document the workflow in README + CLAUDE.md.
5. **Issue #9** — branch protection on `main` (after #8 stabilises the check names).
6. **Back to Phase 1**: issue #2 (`feat(auth): register/login/refresh/me + JWT dependency`).
