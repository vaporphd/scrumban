# Followup

## Status

Branch `main`, in sync with `origin/main`. Phase 0 complete.

Scaffolded: FastAPI + aiogram backend (shared services layout), Vue 3 + TS + Vite frontend, Alembic (empty baseline), Docker Compose stack (postgres/redis/minio/api/bot/frontend), CI (ruff + mypy + pytest + vue-tsc + vitest + vite build), pre-commit, ADR process. `/api/health` wired end-to-end.

No tests running against live services yet — compose has never been run locally. Secrets (`backend/.env`, `TELEGRAM__BOT_TOKEN`) not set. First compose bring-up will be the smoke test.

## Next

1. **Phase 1 — auth.** `User` + `TgLinkCode` models and migration (issue #1).
2. Auth endpoints: register/login/refresh/me + `current_user` dependency + argon2 hashing + JWT (#2).
3. Frontend auth: Login/Register/Profile views, Pinia auth store, token persistence, axios/fetch interceptor (#3).
4. Auth test suite: register, login, refresh, 401 paths, Telegram link code generation (#4).
5. After Phase 1 merges: update `tasks/todo.md` checkboxes, replace this file with Phase 2 plan.
