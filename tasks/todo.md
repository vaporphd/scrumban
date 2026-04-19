# Scrumban — Project Plan

Kanban-доска для одной организации + Telegram-бот. Python/FastAPI backend, Vue 3 frontend, PostgreSQL, aiogram 3, WebSocket realtime.

---

## 1. Decisions (locked)

- **Scope**: одна организация, несколько досок/проектов, member+owner роли
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + Alembic
- **Frontend**: Vue 3 + TypeScript + Vite + Pinia, Vue DnD для drag-n-drop
- **DB**: PostgreSQL 16
- **Cache / pub-sub / FSM**: Redis 7
- **Bot**: aiogram 3.x, inline keyboards + команды
- **Auth**: username + password (argon2) + JWT access/refresh, без email
- **TG-линковка**: одноразовый 6-значный код из web UI → `/start <code>` в боте
- **Realtime**: WebSocket через FastAPI, broadcast через Redis pub/sub
- **File storage**: MinIO (S3-совместимый), локально в compose
- **Scheduler**: APScheduler (напоминалки о дедлайнах) — запускается в боте
- **Deploy**: Docker Compose на VPS, Nginx reverse proxy, TLS через Caddy или certbot
- **Quality**: ruff + mypy + pytest (httpx AsyncClient) + pre-commit
- **CI**: GitHub Actions — lint, type-check, tests, build images

---

## 2. Architecture

```
┌────────────┐    ┌─────────────────────────────────────┐
│  Vue SPA   │◄──►│  FastAPI (api service)              │
│ (browser)  │ WS │  - REST /api/*                      │
└────────────┘    │  - WebSocket /ws                    │
                  │  - JWT auth                         │
                  └──────┬──────────────────────────┬───┘
                         │                          │
                   ┌─────▼────┐              ┌──────▼────┐
                   │ Postgres │              │   Redis   │
                   └─────▲────┘              │ pub/sub + │
                         │                   │   FSM     │
                  ┌──────┴──────────┐        └──────▲────┘
                  │ aiogram bot     │               │
                  │ (bot service)   ├───────────────┘
                  │ + APScheduler   │
                  └──────┬──────────┘
                         │
                    ┌────▼────┐
                    │  MinIO  │  (attachments)
                    └─────────┘
```

**Ключевой паттерн**: api и bot — два процесса, общий доменный слой (`domain/`, `repositories/`, `services/`). Оба пишут в Postgres и публикуют события в Redis (`board:{id}` channel). WS-connection-manager в api слушает Redis и пушит события в подключённых клиентов.

---

## 3. Data model (первая версия)

- `users`: id, username (uniq), password_hash, display_name, tg_user_id (nullable, uniq), tg_username, role (owner/member), created_at
- `tg_link_codes`: user_id, code (6 digits), expires_at
- `boards`: id, name, description, created_by, created_at, archived_at
- `columns`: id, board_id, name, position (int), wip_limit (nullable)
- `tasks`: id, column_id, title, description (markdown), creator_id, assignee_id (nullable), priority (enum: low/med/high/urgent), due_at (nullable), position (int), created_at, updated_at, completed_at
- `labels`: id, board_id, name, color
- `task_labels`: task_id, label_id (m2m)
- `comments`: id, task_id, author_id, body, created_at, edited_at
- `attachments`: id, task_id, uploader_id, storage_key, filename, mime, size, created_at
- `activity_log`: id, board_id, task_id, user_id, action, payload_json, created_at

Индексы: `tasks(column_id, position)`, `tasks(assignee_id, due_at)`, `activity_log(board_id, created_at desc)`, `comments(task_id, created_at)`.

---

## 4. Repo layout

```
scrumban/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── bot/            # aiogram handlers, FSM, scheduler
│   │   ├── core/           # config, security, logging, deps
│   │   ├── domain/         # pydantic models / enums
│   │   ├── db/             # SQLAlchemy models, session, migrations
│   │   ├── repositories/   # data access
│   │   ├── services/       # business logic (shared api+bot)
│   │   ├── realtime/       # WS manager + Redis pub/sub
│   │   ├── storage/        # MinIO client
│   │   └── main_api.py / main_bot.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/          # Board, Login, Settings
│   │   ├── components/     # Column, TaskCard, TaskModal, etc.
│   │   ├── stores/         # pinia: auth, board, ws
│   │   ├── api/            # REST client
│   │   ├── ws/             # WebSocket client
│   │   └── router/
│   ├── package.json
│   └── Dockerfile
├── deploy/
│   ├── docker-compose.yml
│   ├── nginx.conf (or Caddyfile)
│   └── .env.example
├── thoughts/               # conversation logs (gitignored)
├── tasks/                  # todo.md, lessons.md (gitignored)
├── .github/workflows/ci.yml
└── README.md
```

---

## 5. Phases & tasks

### Phase 0 — Foundation (день 1–2) ✅
- [x] Инициализировать репо, `.gitignore` (вкл. `thoughts/`)
- [x] `backend/pyproject.toml` (FastAPI, SQLAlchemy async, Alembic, aiogram 3, pydantic-settings, argon2-cffi, python-jose, redis, aioboto3, APScheduler, structlog)
- [x] `frontend/` — Vue 3 + TS + Vite + Pinia + Vue Router + Vitest
- [x] `deploy/docker-compose.yml`: postgres 16, redis 7, minio + api/bot/frontend сервисы
- [x] `alembic.ini` + `alembic/env.py` (async engine), пустой `versions/`
- [x] `core/config.py` с pydantic-settings (env_nested_delimiter="__")
- [x] `core/logging.py` (structlog JSON)
- [x] `db/base.py` (Base + TimestampMixin), `db/session.py` (async engine/sessionmaker)
- [x] `api/health.py` (`GET /api/health`) + test
- [x] `main_api.py` (FastAPI + CORS + lifespan), `main_bot.py` (aiogram 3 + Redis FSM)
- [x] ruff + mypy + pytest конфиг в pyproject
- [x] .pre-commit-config.yaml (ruff + базовые хуки)
- [x] GitHub Actions CI: ruff, mypy, pytest, vue-tsc, vitest, vite build
- [x] Dockerfile backend (slim, non-root, healthcheck) + frontend (multi-stage nginx)
- [x] README с dev-flow, командами, архитектурой

### Developer experience (cross-phase)
- [x] 7 Claude Code subagent profiles wired into the issue-driven flow (#13, #15)
- [x] `followup.md` hardened as a hard gate (#18)
- [x] Smoke-tester agent + Playwright e2e baseline (#24)
- [x] Autonomous pre-merge review loop codified in CLAUDE.md + reviewer/implementer agents (#29)
- [x] Reviewer should-fix is non-negotiable; no tech-debt deferral (#32)
- [x] Pin ruff to the same exact version across pre-commit, CI, and pyproject.toml (#33)
- [x] Fully autonomous loop — auto-merge on clean approve, nits are bugs, required smoke coverage, smoke-fail → implementer (#38)
- [x] Pre-merge loop quick-reference doc at `docs/loop.md` + cross-link from `CLAUDE.md` (#40)
- [x] Playwright e2e wired into CI as a separate `e2e` job — postgres + redis services, host-side uvicorn + vite, cached chromium, failure artifacts (#26)
- [x] Pre-push pytest resolves postgres host via localhost by default — `backend/.env.local` override loaded after `.env` by pydantic-settings (#67)
- [x] Pre-push hook refuses direct pushes to `main` unless diff is pure docs (`docs/`, `thoughts/`, `tasks/`, `*.md` at root) — test harness at `scripts/test-no-verify-guard.sh` (#68)

### Phase 1 — Auth + users (день 3–4)
- [x] SQLAlchemy модели: `User`, `TgLinkCode` (#1, merged `3dd6cf6`)
- [x] Миграция (#1, `5130146827ca`)
- [x] `POST /api/auth/register` (username+password, argon2) (#2)
- [x] `POST /api/auth/login` → access+refresh JWT (#2)
- [x] `POST /api/auth/refresh` (#2, opaque rotating tokens per ADR-0005)
- [x] `GET /api/me` (#2)
- [x] FastAPI dependency `current_user` (Bearer JWT) (#2)
- [x] Vue: Login / Register / страница профиля (#3)
- [x] Тесты: регистрация, логин, 401 без токена, refresh-flow (#4) — 17 tests, 99% coverage on `auth_service.py`
- [x] Hardening: close username-enumeration timing leak in `authenticate()` — dummy argon2 verify on user-not-found branch + strict timing-parity assertion (#23)
- [x] Telegram link-code endpoint (`POST /api/me/tg-link-code`) + Profile "Link Telegram" UI; `UserRead` / frontend `User` gain `tg_user_id` + `tg_username` (#20)

### Phase 2 — Boards + columns + tasks CRUD (день 5–8)

**Fine-grained issue queue**: issues #36, #67-#122 split the checkboxes below into 55+ single-PR tasks (backend endpoints split per verb/resource, frontend split per component / interaction, tests split per resource). Lowest-numbered open issue is the next actionable item. Phase 3 realtime in #123-#134.

- [x] Модели: `Board`, `Column`, `Task`, `Label`, `TaskLabel` (#36)
- [x] Миграция (#36, `73cb93ca2565`)
- [x] Репо-слой + сервисы (переиспользуемые api+bot) (#36, read-only repo + NotImplementedError service skeletons)
- [ ] REST: `/api/boards` (list/create/get/update/archive)
- [ ] REST: `/api/boards/{id}/columns` (CRUD + reorder)
- [ ] REST: `/api/boards/{id}/tasks` (list с фильтрами: assignee, label, due, search)
- [ ] REST: `/api/tasks/{id}` (get/update/delete)
- [ ] REST: `/api/tasks/{id}/move` (column_id + position) — с транзакционным пересчётом позиций
- [ ] REST: `/api/boards/{id}/labels` CRUD
- [ ] Vue: Board view с колонками + TaskCard
- [ ] Vue: TaskModal (просмотр + инлайн-редактирование)
- [ ] Vue: drag-n-drop с оптимистичным UI → вызов `/move`
- [ ] Тесты: CRUD + реордеринг

### Phase 3 — Realtime (день 9–10)
- [ ] `realtime/connection_manager.py`: WS-соединения по board_id
- [ ] `realtime/events.py`: типизированные события (`task.created`, `task.moved`, `task.updated`, `comment.added`, …)
- [ ] Redis pub/sub: сервисы публикуют, WS subscriber пересылает подключённым
- [ ] `WS /ws?board_id=X` с JWT-проверкой при connect
- [ ] Vue: WS-стор, мердж входящих событий в board-state
- [ ] Тесты: два клиента, изменение в одном → видно во втором

### Phase 4 — Telegram bot (день 11–14)
- [ ] aiogram bootstrap в отдельном сервисе, FSM в Redis
- [ ] `/start <code>` — линковка TG к user через `TgLinkCode`
- [ ] UI в профиле: «Привязать Telegram» → генерим код, показываем кнопку-ссылку `t.me/<bot>?start=<code>`
- [ ] `/boards` — список, inline-кнопки для выбора → сохраняем «текущую доску» в FSM
- [ ] `/tasks` — задачи текущей доски, фильтр (мои / все / overdue), inline-пагинация
- [ ] `/today` — дедлайны сегодня
- [ ] `/new` — FSM-визард: title → board → column → optional due/assignee
- [ ] Клик по задаче → карточка с кнопками: ← Move, 💬 Comment, ✅ Done, 👤 Assign
- [ ] Reply-на-карточку → добавить комментарий
- [ ] Все действия идут через те же `services/*` что и REST → триггерят те же Redis-события
- [ ] Тесты: моки aiogram dispatcher + реальный сервисный слой

### Phase 5 — Attachments (день 15–16)
- [ ] MinIO клиент, bucket `attachments`, pre-signed URL генерация
- [ ] `POST /api/tasks/{id}/attachments` (multipart) → сохраняем, возвращаем метаданные
- [ ] `GET /api/attachments/{id}/download` → redirect на presigned URL
- [ ] Vue: drag-n-drop файлов в TaskModal + галерея превью
- [ ] Bot: фото/документ в reply на задачу → прикрепляем
- [ ] Ограничения: макс размер (напр. 20MB), whitelist mime

### Phase 6 — Reminders + activity (день 17–18)
- [ ] APScheduler job в bot-сервисе: раз в минуту ищет `due_at - now < reminder_window AND notified_at IS NULL AND assignee.tg_user_id IS NOT NULL`
- [ ] Отправляет DM ассайни, помечает `notified_at`
- [ ] `@mentions` в комментариях: парсим `@username`, шлём DM в TG если привязан
- [ ] `activity_log` заполняется сервисным слоем на ключевых действиях
- [ ] Vue: панель «Активность» на доске
- [ ] Bot: `/digest` — утренний дайджест задач (опц.)

### Phase 7 — Polish + ship (день 19–21)
- [ ] RBAC: owner может приглашать/удалять members, member не может удалять доски
- [ ] Инвайты: owner создаёт одноразовую ссылку регистрации
- [ ] Rate limiting (slowapi) на auth + бот
- [ ] Sentry (backend + frontend), structlog JSON-логи
- [ ] Docker images: multi-stage, non-root, healthchecks
- [ ] `docker-compose.prod.yml` + Caddy с авто-TLS
- [ ] README: установка, запуск локально, деплой на VPS, env-переменные
- [ ] Backup-скрипт для Postgres (cron в compose)
- [ ] Smoke-тест e2e: регистрация → создание доски → задача → движение → бот → WS

---

## 6. Open questions (уточнить когда дойдём)

- Нужен ли аудит-лог для GDPR / для отката? (`activity_log` сейчас append-only)
- Webhook для бота (prod) vs long-polling (dev) — настроить оба режима через env
- i18n: только русский или нужен EN? (пока RU-only)
- Markdown в описаниях/комментариях — какой рендер на фронте (markdown-it?) и как в TG (MarkdownV2)?

---

## 7. Что ещё стоит помнить (реко из планирования)

- **Position как float** при DnD проще, чем пересчёт целых `ORDER` — вставляем между соседями как `(prev+next)/2`, периодически rebalance-им. Меньше write-amplification.
- **Idempotency-key** на `POST /tasks` полезен — бот может ретраить.
- **Webhook secret** для TG в prod — проверяй `X-Telegram-Bot-Api-Secret-Token`.
- **WS auth** — не отдавай JWT в query в логах; либо в первом `subscribe`-сообщении, либо cookie.
- **N+1** на Board view: грузи задачи + labels + assignees одним запросом (joinedload/selectinload).
- **Pydantic v2** — выставляй `model_config = ConfigDict(from_attributes=True)` для схем ответа.
- **Тесты бота**: aiogram даёт `MockedBot` + `TestClient` для dispatcher — используй, не мокай телеграм SDK вручную.

---

## 8. Review (заполнится по мере реализации)

_(пусто)_
