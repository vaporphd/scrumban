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
4. **Branch protection** on `main`: required checks `backend` and `frontend` must be green to merge; linear history required (squash/rebase, no merge commits); force-push and branch-delete blocked; conversation resolution required on PRs. Admin (repo owner) can still push trivial direct commits while the project is solo — enable `enforce_admins` when the team grows.

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
- Hook + CI ruff versions are pinned to the same exact tag in `.pre-commit-config.yaml` (`ruff-pre-commit v0.15.11`), `.github/workflows/ci.yml` (`pip install ruff==0.15.11`), and `backend/pyproject.toml` (`ruff==0.15.11`). Bump them together. Drift forces `SKIP=ruff-format` bypasses — same family as `--no-verify` per below.
- Same pin-everywhere rule applies to the rest of the backend dev tools: `mypy`, `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `types-python-jose`. Exact `==` pins live in `backend/pyproject.toml` `[dependency-groups].dev` and are mirrored in the `Install dependencies` step of `.github/workflows/ci.yml`. Bumping any of them is a two-file change — keep the versions identical or CI will resolve a different set than the local venv and drift will resurface as "green locally, red in CI".

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

Every PR that closes an issue **must**:

1. **Update `followup.md`**.
   - `Status` is rewritten as if the PR is **already merged** — describe the new reality, not a plan.
   - `Next` lists **3+ concrete priorities with issue numbers**. No placeholders like "TBD", "various improvements", or "polish". If there's genuinely nothing queued, open the next issue first and then land the PR.
   - Replace the whole file — do not append. History lives in `git log`; `followup.md` is a snapshot.

2. **Tick the corresponding checkbox(es) in `tasks/todo.md`** for items this PR lands. Do not delete ticked items — they are the record of work done.

A PR that introduces a new subsystem or makes an architectural choice **additionally must** include one of:
- A new ADR under `docs/adr/NNNN-title.md` (sequential numbering, format: Status / Date / Context / Decision / Reasoning / Consequences), OR
- An update to an existing ADR (mark superseded if replaced), OR
- A corresponding checklist update in `tasks/todo.md` if the plan already covered it.

"New subsystem" means: a new top-level `app/` package, a new external service dependency, a new auth/permission mechanism, a new protocol (WS event type, bot command family), a new storage backend. When in doubt — write the ADR.

**Reviewer blocks on a missing or stale `followup.md` update** — `must-fix`, not a nit. Without this, cross-session memory decays and the next session starts with stale priorities.

### gh CLI cheatsheet

```sh
gh issue create --title "feat: ..." --label "phase/1,type/feat,area/auth" --body "..."
gh issue list --label "phase/1"
gh issue view N
gh pr create --fill                    # uses latest commit message
gh pr view --web
gh pr checks
```

## Agent ownership

Eight specialized subagents live in `.claude/agents/*.md`. Each has a narrow scope, a tool whitelist, and a required response format. The top-level session **delegates** to them via the `Task` tool.

| Stage of the flow               | Agent          | Trigger                                                         |
|---------------------------------|----------------|-----------------------------------------------------------------|
| Understand existing code        | `explorer`     | "how does X work", "trace X", "where is X implemented"          |
| Design a new subsystem + ADR    | `architect`    | new `app/` package, new external dep, new protocol, new authz   |
| Take issue #N → branch → PR     | `implementer`  | "implement #N", "take on issue #N"                              |
| Fix a reported bug              | `bug-hunter`   | bug report with symptom; starts with failing regression test    |
| Smoke-test a PR end-to-end      | `smoke-tester` | frontend changes — proactive after `implementer` opens PR, before `reviewer` |
| Pre-merge review                | `reviewer`     | **proactive** — run before any `gh pr merge`                    |
| Hooks / workflows / compose     | `ci-devops`    | touching `.github/`, `.pre-commit-config.yaml`, `deploy/`, Dockerfiles |
| Sync docs with code             | `docs-writer`  | **proactive** — after a PR that changes setup, commands, or conventions |

### Delegate vs handle directly

The main session **delegates** these:

- Any non-trivial read-only investigation (> 3 files or > 5 minutes of grep) → `explorer`
- Any production code change scoped to a single issue → `implementer`
- Any bug report with a reproducer → `bug-hunter`
- Any PR that touches `frontend/` → `smoke-tester` (after `implementer`, before `reviewer`)
- Every PR before `gh pr merge` → `reviewer`
- Any CI / hook / infra change → `ci-devops`
- Any docs update driven by a code change → `docs-writer` (may run proactively after merges)
- Any design choice that warrants an ADR → `architect`

The main session **handles directly** (never delegates):

- Clarifying requirements with the user (`AskUserQuestion`).
- Authorizing destructive actions (`gh pr merge`, `git push --force`, `gh api -X DELETE …`). The user authorizes, the main session executes.
- Coordinating multi-agent workflows (e.g. architect → implementer → reviewer on a multi-PR epic).
- Reading and writing `followup.md` between agent handoffs.
- Escalating when an agent reports a blocker it cannot resolve.

### How to invoke

Explicit:
```
Task(subagent_type="implementer", prompt="Take on issue #2: ...")
Task(subagent_type="reviewer",    prompt="Review PR #N")
```

Implicit (proactive): the agent's `description` field triggers automatic delegation on matching phrasing — e.g. "please review PR #14" picks `reviewer`, "how does our auth work" picks `explorer`. Keep prompts phrased like the triggers so delegation is deterministic.

### Invariant

Every PR produced by an agent still goes through the three-layer quality gate (pre-commit, pre-push, CI) and branch protection on `main`. Agents don't get a bypass — they just do the work, and the gate checks the output.

### Pre-merge review loop (fully autonomous — zero routine user questions)

When the implementer finishes a PR, the main session runs this loop **without asking the user between steps or at the end**. Authorization 2026-04-17: auto-merge is enabled for PRs produced through this loop. The user interrupts only to pivot or when an agent reports a blocker.

Quick-reference diagram: [`docs/loop.md`](docs/loop.md).

1. Implementer reports `ready to merge pending authorization` → main session **immediately** delegates to `smoke-tester` (for any PR that carries a Playwright spec — per the 2026-04-19 rule that's effectively every non-pure-infra PR, including backend-only ones whose specs live under `frontend/tests/e2e/api/*.spec.ts`) or `reviewer` (if truly pure infra — CI configs / Dockerfiles / agent descriptions / pure docs). Do not ask "should I run reviewer?" — the answer is always yes.

2. On `smoke-tester` `green` → main session immediately delegates to `reviewer`. On `smoke-tester` `reproduced, handoff to implementer` → main session **immediately** delegates to `implementer` with the smoke artifacts (failing scenario name, first 30 lines of failure output, artifact directory path) as the brief. Implementer fixes the regression on the same branch; loop re-enters at step 1 (smoke-tester re-runs against the new commit). **No new issue is filed** — the failing spec IS the reproducer; the fix belongs in this PR. If implementer determines the failure is pre-existing (not caused by this PR's diff), they escalate to `bug-hunter` with the artifacts and pause this PR — that's an exception path, the implementer's call based on `git diff`, not the main session's default route.

3. On `reviewer` verdict `changes-requested` — **any** finding at ANY severity (must-fix, should-fix, OR nit) triggers this verdict — main session **immediately** delegates back to `implementer` with the findings. Do not ask "should I send these back?" — the answer is always yes. No deferrals at any severity: the reviewer is forbidden from downgrading any finding to non-blocking (`reviewer.md` "Verdict ↔ findings consistency"), and nits are no longer a user judgment call — they route through the same loop as must-fix/should-fix (authorization 2026-04-17: "suggestions should be treated as a bug"). If a finding genuinely requires out-of-PR work, a blocking issue is opened first; the verdict stays `changes-requested`. The reviewer is responsible for posting findings to the linked issue (see `reviewer.md`).

4. `approve-with-suggestions` is deprecated by authorization 2026-04-17. If the reviewer returns this verdict, the main session treats it as `changes-requested` — the findings are authoritative, the verdict label is wrong, route to implementer. Prefer `approve` (literally zero findings) or `changes-requested` (any findings at any severity) as the clean binary.

5. On `reviewer` verdict `approve` (literally zero findings — no must-fix, no should-fix, no nits) → main session **immediately** runs `gh pr merge N --auto --squash --delete-branch`. GitHub waits for CI green (if not already) and merges; branch is deleted; linked issue auto-closes via `Closes #N` in the PR body. **No user question.** This is a per-project authorization Alex granted on 2026-04-17 ("you merge once task is done, reviewed and merged" + "automerge if review (no nits, no nothing, all clean), all tests and smoke passed") that overrides CLAUDE.md's default destructive-action gate on `gh pr merge`. If auto-merge fails (conversation-resolution blocker, rebase conflict), main session resolves and retries; if unresolvable, escalates to user. Authorization scope: PRs produced through the implementer → reviewer agent loop. External PRs (dependabot, outside contributors once team grows) still require user merge auth.

6. After implementer pushes a review-fix commit → main session **immediately** re-invokes `reviewer` (and `smoke-tester` first if frontend/feature changed). Loop until step 5 (auto-merge) or an agent reports an unresolvable blocker.

The loop terminates only at step 5 (auto-merge executes) or when an agent reports a blocker. The user can always interrupt and pivot at any step.

### Automated /loop mode — issue pickup

When the user starts a `/loop` session (or uses one of the trigger phrases below), the main session auto-picks the next issue rather than waiting for a `do #N` instruction. Pickup rules:

1. **Default policy — lowest-numbered open issue, dependency-ordered**. Run:
   ```sh
   gh issue list --state open --json number --jq '[.[].number] | min'
   ```
   The queue (#67-#134) was filed in strict dependency order; lowest-open-number ≈ next-unblocked-work. Simple and reliable.

2. **Exceptions the main session applies without asking**:
   - If the lowest-open issue is a `test(api): *` issue that depends on the associated feature endpoints being merged, verify those are closed first. If not, skip to the next issue and flag to the user.
   - If the issue is blocked by an unresolved blocker issue (main session files these when smoke-tester reports pre-existing fails), skip.

3. **User override**: at any time the user can say `do #N` or `skip to #M` — main session switches context immediately and rewinds the queue afterward.

4. **Between iterations, main session re-reads**: `CLAUDE.md` "Pre-merge review loop", `tasks/lessons.md`, and the last 5 lines of `followup.md Status` so context doesn't drift after compaction.

5. **Stop conditions**:
   - No open issues remain → report "queue drained" and stop.
   - Agent reports blocker the main session can't resolve → report + stop.
   - User interrupts → stop on next safe checkpoint (after current PR merges or hits a review loop).
   - Token budget approached (if /loop dynamic mode signals) → finish current PR, then pause.

6. **Cross-iteration invariant**: the main session does not hold state across `/loop` wakeups — everything must be rederivable from `gh issue list`, `gh pr list`, `followup.md`, and the agent files on disk. Do not rely on "I remember we were working on #69" — re-derive.

### Trigger phrases — recognize in user messages

The main session treats the following natural-language phrases as loop invocations without waiting for an explicit `/loop` slash command. **Match case-insensitive, tolerant of minor rewording** (e.g. "next", "the next", "a batch of", "a few" all count). Whenever the user is asking the session to run the agent loop autonomously on the queue, this section applies.

| Phrase pattern                                      | Iterations (N)                                    |
|-----------------------------------------------------|---------------------------------------------------|
| `take next task` / `do next task` / `run next task` / `do the next one` | 1 (single PR, then pause)                         |
| `take next N tasks` / `do next N tasks` / `run next N` / `do N more` | N (where N is the integer in the message)        |
| `do all next tasks` / `take all` / `run all open` / `drain the queue` / `keep going until done` | unbounded (until queue drained, blocker, or user interrupt) |
| `/loop` (slash skill) / `run the loop` / `start the loop` | unbounded dynamic mode — use the `/loop` skill and let it self-pace across session wakeups |

**Reporting contract during a multi-PR loop**:

- Before starting, confirm the plan in one line: `Picking up N tasks starting from issue #X. First: <title>.`
- Between merges, emit a single-line progress update: `Merged K/N (#Y closed). Next: #Z <title>.` No narration.
- On blocker: `Merged K/N. Stopping on issue #Y: <blocker summary>. User action needed.` Then stop — do not continue to issue #Y+1 on the assumption the blocker will resolve itself.
- On queue drained before N reached: `Merged K of requested N (queue drained at #last-issue). No more open issues matching the queue criteria.` Stop.
- On user interrupt: finish the currently-in-flight PR to the next safe checkpoint (auto-merge or review-loop boundary), then stop with a status summary.

**Counting invariant**: N counts **merged PRs**, not attempted PRs. A PR that gets blocked mid-loop does not decrement the counter; the loop resumes where it stopped when the blocker is cleared.

**Authorization scope for unbounded mode**: `do all next tasks` inherits the same auto-merge authorization from ADR-0007 — the session can run arbitrarily many autonomous PRs through the implementer → smoke-tester → reviewer → auto-merge chain without per-PR user input, until one of the stop conditions above fires. The safety gates (CI green, smoke green, reviewer zero findings) remain per-PR; the unbounded count just removes the outer "should I start the next one?" question.

**Ambiguous phrasing**: if the number is unclear ("do a few", "take a couple"), ask once. Do not guess `3` silently. Similarly, if the phrase could plausibly mean "just tell me about the next tasks" (informational) rather than "execute them" (loop), ask. The agent loop is destructive (PRs merged to `main`) — explicit invocation matters.
