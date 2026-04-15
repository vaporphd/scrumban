# Scrumban

Kanban board with a Telegram bot. Web UI (Vue 3) + REST/WS API (FastAPI) + aiogram bot, shared domain layer, PostgreSQL, Redis, MinIO.

Full project plan lives in [`tasks/todo.md`](tasks/todo.md).

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, aiogram 3, APScheduler, Redis, MinIO
- **Frontend**: Vue 3, TypeScript, Vite, Pinia, Vue Router
- **Infra**: Docker Compose (PostgreSQL 16, Redis 7, MinIO)
- **Quality**: ruff, mypy, pytest, pre-commit, GitHub Actions CI

## Repo layout

```
backend/           FastAPI app, aiogram bot, shared services, Alembic migrations
frontend/          Vue 3 SPA
deploy/            docker-compose for dev & prod
tasks/             plan, lessons
.github/workflows/ CI
```

## Local dev

### With Docker Compose (recommended)

```sh
cp backend/.env.example backend/.env
# edit backend/.env — set TELEGRAM__BOT_TOKEN if you want the bot

cd deploy
docker compose up -d postgres redis minio
docker compose up api bot frontend
```

Services:
- API: http://localhost:8000 (health: `/api/health`, docs: `/docs`)
- Frontend: http://localhost:5173
- Postgres: `localhost:5432` (user/pass/db = `scrumban`)
- Redis: `localhost:6379`
- MinIO: http://localhost:9001 (console, admin/admin)

### Backend standalone

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install ruff mypy pytest pytest-asyncio

# migrations
alembic upgrade head

# api
uvicorn app.main_api:app --reload

# bot (separate terminal)
python -m app.main_bot
```

### Frontend standalone

```sh
cd frontend
npm install
npm run dev
```

## Developer onboarding

One-time setup after cloning:

```sh
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e . && pip install ruff mypy pytest pytest-asyncio httpx pre-commit && cd ..
cd frontend && npm install && cd ..
pre-commit install                        # wires git hooks: pre-commit AND pre-push
```

## Quality gate

What runs where:

| Stage              | When                | Runs                                                              | Time      |
|--------------------|---------------------|-------------------------------------------------------------------|-----------|
| **pre-commit**     | `git commit`        | ruff check, ruff format, mypy (backend), vue-tsc (frontend)       | < 5s      |
| **pre-push**       | `git push`          | pytest (backend), vitest (frontend)                               | 5–20s     |
| **CI**             | PR + push to `main` | all of the above + `alembic upgrade/downgrade` round-trip + vite build, against a live Postgres service container | 2–3 min  |
| **branch protection** | PR merge         | `main` refuses merges unless CI is green                          | —         |

`--no-verify` bypasses the hooks. Use it for emergencies only — never for a commit that will be merged to `main`.

## Common commands

Backend:
```sh
cd backend
ruff check . && ruff format .
mypy app
pytest
pytest tests/test_health.py::test_health_ok   # single test
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Frontend:
```sh
cd frontend
npm run type-check
npm run test
npm run build
```

## Agent profiles

Committed to `.claude/agents/` — seven specialized Claude Code subagents with narrow scopes, tool whitelists, and required response formats:

| Agent | What it does |
|---|---|
| `explorer` | trace code before changing it; read-only |
| `architect` | design + ADRs; no production code |
| `implementer` | one issue end-to-end; no merges, no scope creep |
| `bug-hunter` | failing regression test first, then minimum fix |
| `reviewer` | pre-merge PR review; posts comments, never pushes |
| `ci-devops` | hooks, workflows, compose, Dockerfiles — not app code |
| `docs-writer` | README / CLAUDE.md / ADRs / followup in sync with code |

Claude Code picks one automatically based on the task, or you can delegate explicitly with the `Task` tool.

## Architecture at a glance

Two Python processes (`api`, `bot`) share the same package (`app/`):
- `app/api/` — FastAPI routers (REST + WS)
- `app/bot/` — aiogram handlers, FSM, scheduler
- `app/services/` — business logic, used by both
- `app/repositories/` — data access
- `app/realtime/` — WS connection manager backed by Redis pub/sub

Any mutation (from web or bot) goes through a service → publishes an event to Redis → every connected WS client on the affected board gets it. This is the glue between the two surfaces.

Telegram linking: user generates a 6-digit code in the web profile, sends `/start <code>` to the bot. Until linked, the bot refuses anything beyond `/start`.
