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

### Phase 0 — Foundation (день 1–2)
- [ ] Инициализировать репо, `.gitignore` (вкл. `thoughts/`, `tasks/`)
- [ ] `backend/pyproject.toml` с FastAPI, SQLAlchemy, Alembic, aiogram, pydantic-settings, argon2-cffi, python-jose, aioredis, aiobotocore, APScheduler
- [ ] `frontend/` — `pnpm create vue@latest`, выбрать TS + Pinia + Vue Router
- [ ] `deploy/docker-compose.yml`: postgres, redis, minio (dev)
- [ ] `alembic init` + первый ревижн (пустой baseline)
- [ ] Скелет `core/config.py` с pydantic-settings (читает `.env`)
- [ ] ruff + mypy + pre-commit hooks
- [ ] GitHub Actions: lint + type-check + pytest

### Phase 1 — Auth + users (день 3–4)
- [ ] SQLAlchemy модели: `User`, `TgLinkCode`
- [ ] Миграция
- [ ] `POST /api/auth/register` (username+password, argon2)
- [ ] `POST /api/auth/login` → access+refresh JWT
- [ ] `POST /api/auth/refresh`
- [ ] `GET /api/me`
- [ ] FastAPI dependency `current_user` (Bearer JWT)
- [ ] Vue: Login / Register / страница профиля
- [ ] Тесты: регистрация, логин, 401 без токена, refresh-flow

### Phase 2 — Boards + columns + tasks CRUD (день 5–8)
- [ ] Модели: `Board`, `Column`, `Task`, `Label`, `TaskLabel`
- [ ] Миграция
- [ ] Репо-слой + сервисы (переиспользуемые api+bot)
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
