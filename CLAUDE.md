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

### Git / CI

CI runs on push/PR to `main`: ruff, mypy, pytest (backend) + vue-tsc, vitest, vite build (frontend). Both must pass.

`pre-commit install` (optional) wires ruff + whitespace hooks.

## Conventions specific to this repo

- `tasks/todo.md` is tracked in git and kept up to date with the plan; `thoughts/` is gitignored (session logs).
- Services are stateless — put scheduled work in `app/bot/` via APScheduler (the bot process owns the scheduler, not api).
- Publish Redis events from services, never directly from routers/handlers.
- New endpoints go under `app/api/`; new bot commands under `app/bot/handlers/`. Both call into `app/services/`.
- Ruff rule `ASYNC` is on — don't block the event loop (`time.sleep`, sync DB calls, sync file IO in handlers).
- Mypy is `strict`. Prefer `pydantic` models for request/response, not raw dicts.
