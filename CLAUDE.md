# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Kanban board + Telegram bot. Single organization, multiple boards, realtime sync between web UI and bot. Team of up to a few dozen users.

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, aiogram 3, APScheduler, Redis, MinIO
- **Frontend**: Vue 3 + TypeScript, Vite, Pinia, Vue Router
- **Infra**: Docker Compose for dev and VPS prod

The full phased implementation plan lives in `tasks/todo.md` — read it before adding features; it's the source of truth for scope and sequencing. Mark items complete there as you land them.

## Architecture (the big picture)

Two Python processes — **api** (FastAPI) and **bot** (aiogram) — share the same package `backend/app/`. They are NOT separate codebases:

```
app/api/          REST + WebSocket routers (FastAPI)
app/bot/          aiogram handlers, FSM, APScheduler jobs
app/services/     business logic used by both api AND bot
app/repositories/ data access (SQLAlchemy)
app/realtime/     WS connection manager backed by Redis pub/sub
app/domain/       pydantic schemas, enums
app/db/           SQLAlchemy models, Base, session
app/core/         config, logging, security
app/main_api.py   FastAPI entrypoint
app/main_bot.py   aiogram entrypoint
```

**Key invariant**: every mutation (from HTTP handler OR bot handler) goes through `app/services/*`. Services publish events to Redis (`board:{id}` channel). The WS manager subscribes and fans events out to connected web clients. This is what keeps web and Telegram in sync.

Do not duplicate business logic between api and bot. If you find yourself writing the same thing in a bot handler and an HTTP handler, extract a service.

**Telegram linking**: a user is bound to a `tg_user_id` via a one-time 6-digit code generated in the web profile and sent as `/start <code>`. Bot handlers must refuse anything beyond `/start` until the caller is linked. Never trust `tg_user_id` from an unlinked message as identity.

**Auth**: username + password (argon2) + JWT (access + refresh). No email. JWT in `Authorization: Bearer`. WS authenticates on connect.

**Task ordering in columns**: use float `position` and insert between siblings as `(prev + next) / 2`. Periodic rebalance only when positions get too close. Avoid renumbering all rows on every move.

## Config

All settings live in `app/core/config.py` via `pydantic-settings`. Env vars use nested delimiter `__`:

```
DATABASE__URL=postgresql+asyncpg://...
REDIS__URL=redis://...
JWT__SECRET=...
TELEGRAM__BOT_TOKEN=...
STORAGE__ENDPOINT_URL=http://minio:9000
```

`backend/.env.example` is the canonical list. Copy to `backend/.env` for local dev.

## Commands

### Dev loop (docker compose — preferred)

```sh
cd deploy
docker compose up -d postgres redis minio   # infra only
docker compose up api bot frontend          # app services with reload
```

- API: http://localhost:8000 (`/api/health`, `/docs`)
- Frontend: http://localhost:5173
- MinIO console: http://localhost:9001 (minioadmin/minioadmin)

### Backend

```sh
cd backend

# install (editable)
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install ruff mypy pytest pytest-asyncio httpx types-python-jose

# lint + format + types
ruff check .
ruff format .
mypy app

# tests
pytest                                           # all
pytest tests/test_health.py                      # one file
pytest tests/test_health.py::test_health_ok      # one test
pytest -k health                                 # by keyword
pytest --cov=app                                 # coverage

# run services locally
uvicorn app.main_api:app --reload
python -m app.main_bot

# migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

When adding a new SQLAlchemy model, import it in `alembic/env.py` (look for the `# import app.db.models` note) before running `alembic revision --autogenerate`, otherwise it won't appear in the diff.

### Frontend

```sh
cd frontend
npm install
npm run dev          # vite dev server (proxies /api and /ws to :8000)
npm run type-check   # vue-tsc --noEmit
npm run test         # vitest run
npm run test:watch
npm run build        # type-check + vite build
```

Path alias `@/*` → `src/*`.

### Git / CI / quality gate

Three layers enforce a clean `main`:

1. **pre-commit hook** (fast, on `git commit`): ruff check + format, mypy (backend), vue-tsc (frontend).
2. **pre-push hook** (medium, on `git push`): pytest (backend), vitest (frontend).
3. **CI** on push/PR to `main`: all of the above + ruff format `--check`, `alembic upgrade/downgrade` round-trip against a live Postgres service container, vite build.
4. **Branch protection** on `main`: required checks `backend` and `frontend` must be green to merge.

Install both git-hook stages once:
```sh
pre-commit install                        # installs pre-commit AND pre-push, see default_install_hook_types
pre-commit run --all-files                # sanity check
pre-commit run --hook-stage pre-push --all-files
```

**Before opening a PR** — run the same thing CI runs, locally:
```sh
(cd backend && ruff check . && ruff format --check . && mypy app && pytest)
(cd frontend && npm run type-check && npm test && npm run build)
```

**Known gotchas** (things that already bit us — read before assuming the hook is broken):
- `RUF100 unused noqa` — ruff flags `# noqa: XXX` when rule `XXX` isn't in `tool.ruff.lint.select`. Don't add noqa unless the rule is enabled.
- `vitest run` exits 1 on zero test files. `--passWithNoTests` is set while Phase 1 frontend tests are still pending.
- Alembic autogenerate does **not** emit `DROP TYPE` for Postgres ENUMs in `downgrade()`. Add it manually, or round-trip will fail on the second upgrade.
- SQLAlchemy's `sa.Enum(PyEnum, ...)` stores enum **names** (uppercase) by default. Use `values_callable=lambda e: [m.value for m in e]` to store values.
- Pre-commit hooks call `backend/.venv/bin/mypy` and `backend/.venv/bin/pytest` by explicit path. If the venv doesn't exist (or is at a different path), the hook fails. Run the onboarding block from README first.

Bypass via `--no-verify` is for emergencies. Never push `--no-verify` to a branch that will be merged to `main`.

## Conventions specific to this repo

- `tasks/todo.md` is tracked in git and kept up to date with the plan; `thoughts/` is gitignored (session logs).
- `followup.md` in the repo root is the cross-session continuity file: **two sections only** — `Status` and `Next`. Replace, don't append. Update on every merged PR. `git log` is the history, not this file.
- Services are stateless — put scheduled work in `app/bot/` via APScheduler (the bot process owns the scheduler, not api).
- Publish Redis events from services, never directly from routers/handlers.
- New endpoints go under `app/api/`; new bot commands under `app/bot/handlers/`. Both call into `app/services/`.
- Ruff rule `ASYNC` is on — don't block the event loop (`time.sleep`, sync DB calls, sync file IO in handlers).
- Mypy is `strict`. Prefer `pydantic` models for request/response, not raw dicts.

## Issue-driven workflow

Every non-trivial change starts from a GitHub issue. Issues, not chat, are the source of truth for "what are we doing and why". The exception: trivial fixes (typo, one-liner, obvious bug) and items already enumerated in `tasks/todo.md` phase checklists.

### Flow

1. **Create the issue first** (`gh issue create`). Title starts with the type: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`. Body has: what, why, acceptance criteria.
2. Apply labels: one `phase/*`, one `type/*`, one or more `area/*`.
3. **Branch**: `issue-{N}-{slug}` for anything non-trivial. For a solo trunk-based commit against `main`, skip the branch but still reference the issue.
4. **One issue → one PR** when possible. Keep PRs small and focused.
5. **Commits**: `type(scope): description (#N)` — e.g. `feat(auth): add argon2 password hashing (#5)`.
   - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`.
   - Scopes: `api`, `bot`, `ws`, `db`, `auth`, `frontend`, `infra`, `deps`.
6. **Close via PR body**: `Closes #N` (or `Closes #N, #M` for multiple).
7. On merge, update `tasks/todo.md` checkbox + `followup.md` (in the same PR or immediately after).

### Hard gate

A PR that introduces a new subsystem or makes an architectural choice **must** include one of:
- A new ADR under `docs/adr/NNNN-title.md` (sequential numbering, format: Status / Date / Context / Decision / Reasoning / Consequences), OR
- An update to an existing ADR (mark superseded if replaced), OR
- A corresponding checklist update in `tasks/todo.md` if the plan already covered it.

"New subsystem" means: a new top-level `app/` package, a new external service dependency, a new auth/permission mechanism, a new protocol (WS event type, bot command family), a new storage backend. When in doubt — write the ADR.

### gh CLI cheatsheet

```sh
gh issue create --title "feat: ..." --label "phase/1,type/feat,area/auth" --body "..."
gh issue list --label "phase/1"
gh issue view N
gh pr create --fill                    # uses latest commit message
gh pr view --web
gh pr checks
```
