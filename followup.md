# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete. Phase 1 issue #1 merged (`3dd6cf6`): User + TgLinkCode models + Alembic baseline with partial unique index for link-code activity.

Quality-gate epic #11 complete:
- #6 + #7: pre-commit (ruff, mypy, vue-tsc) + pre-push (pytest, vitest) — merged `970a4c0`.
- #8: CI hardened with Postgres service, split steps, npm ci via lockfile — merged `970a4c0`.
- #10: onboarding + quality-gate docs in README + CLAUDE.md — merged `970a4c0`.
- #9: branch protection on `main` — applied via `gh api`, documented in CLAUDE.md.

## Next

1. **Phase 1 — issue #2**: `feat(auth): register/login/refresh/me + JWT dependency`. Argon2 + python-jose + opaque refresh tokens (hashed in DB), service layer in `app/services/auth_service.py`, routers in `app/api/auth.py` + `app/api/me.py`. ADR if the refresh-rotation approach deviates from "rotate on every refresh".
2. **Phase 1 — issue #4**: auth test suite with the live Postgres CI service.
3. **Phase 1 — issue #3**: frontend Login/Register/Profile + Pinia auth store, 401 → refresh interceptor.
4. **Phase 1 — separate ticket**: Telegram link-code endpoint + profile UI button. Small, keep it out of #2 so that PR stays focused.
