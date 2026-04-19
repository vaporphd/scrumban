# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed** — `Board`, `Column`, `Task`, `Label`, `TaskLabel` models, one Alembic migration `73cb93ca2565` with hand-authored `DROP TYPE task_priority` in downgrade (CLAUDE.md gotcha), read-only repositories, and `NotImplementedError`-stubbed service skeletons under `boards_service` / `tasks_service` / `labels_service`. Task `position` is `Float` per ADR-0004; `priority` is a Postgres ENUM with `values_callable` (stores values not enum names, the other CLAUDE.md gotcha). Indexes `ix_tasks_column_id_position` and `ix_tasks_assignee_id_due_at` are in place per `tasks/todo.md` section 3. FK deletion choices: `boards.created_by` → `SET NULL`; `boards → columns → tasks` and `boards → labels` cascade; `tasks.creator_id` / `tasks.assignee_id` → `SET NULL`; `task_labels` cascades on either side. Label names unique-per-board via `uq_labels_board_id_name`. Domain schemas (`Read` / `Create` / `Update`) under `app/domain/{boards,columns,tasks,labels}.py`; hex color pattern enforced in `LabelCreate`. 5 sanity tests under `tests/test_phase2_models.py` cover ORM round-trip, ENUM value storage, m2m, unique constraint, and both cascade directions. Alembic round-trip (`upgrade head → downgrade -1 → upgrade head`) clean. Developer-experience tooling is unchanged — Playwright e2e layer (ADR-0006), autonomous pre-merge review loop (ADR-0007), mandatory Playwright spec (ADR-0008), pinned-ruff invariant, **now extended to all backend dev-deps** (issue 35), compose-aware vite dev proxy, `backend/.env.local` override, pre-push `main-branch-docs-only-guard`.

**Phase 2 issue queue in progress**. With issue 35 closed, the next item is issue 69 — `feat(api): POST /api/boards` (create board) — the first real Phase 2 REST endpoint. It consumes `boards_service.create_board` whose skeleton landed in PR for issue 36.

Merged to `main` (recent — earlier history in `git log`):
- Issue 35 / PR (pending merge) — pinned remaining backend dev-deps to exact `==` versions (`mypy==1.20.1`, `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pytest-cov==7.1.0`, `httpx==0.28.1`, `types-python-jose==3.5.0.20260408`) in `backend/pyproject.toml [dependency-groups].dev`. CI's `Install dependencies` step in `.github/workflows/ci.yml` mirrors the same pins exactly. CLAUDE.md "Known gotchas" extended with a paragraph naming the six dev tools and the pin-everywhere invariant. Tooling-only chore — no new Playwright spec per `tasks/lessons.md` exception list; `npm run e2e` continues to pass unchanged. No `tasks/todo.md` checkbox exists for this DX item.
- Issue 36 / PR 137 — Phase 2 data layer kickoff. Five models under `backend/app/db/models/{board,column,task,label,task_label}.py`; migration `20260419_1001_phase2_boards_columns_tasks_labels.py` with hand-authored `task_priority_enum.drop()` in downgrade; read-only repositories `{board,column,task,label}_repo`; stubbed services `{boards,tasks,labels}_service`; domain schemas `{boards,columns,tasks,labels}.py`; conftest `_clean_db` truncate widened to include all new tables. Smoke: existing `frontend/tests/e2e/api/health.spec.ts` unchanged — schema changes would break the API boot path (SQLAlchemy loads models at import time), so a green health spec is the correct signal for a pure data-layer PR.
- Issue 68 / PR 136 — new pre-push hook `main-branch-docs-only-guard` in `.pre-commit-config.yaml` calling `scripts/pre-push-main-guard.sh`; allow-list is `docs/`, `thoughts/`, `tasks/`, and repo-root `*.md` only. Test harness `scripts/test-no-verify-guard.sh` spins up a throwaway git repo and runs 5 cases. Known limit documented in the hook header: git's `--no-verify` bypasses all client hooks, so server-side enforcement requires a GitHub ruleset out of scope for this DX-layer issue.
- Issue 67 / PR 135 — `backend/.env.local` override loaded after `.env` by pydantic-settings; compose `env_file` untouched; `.env.local.example` template tracked; README + `CLAUDE.md → implementer.md` canonical-fix note updated; mandatory smoke spec `frontend/tests/e2e/api/health.spec.ts` added (Playwright `request` context, no browser). Pre-push pytest now passes on the host shell without the `DATABASE__URL=... git push` prefix.
- **DX pre-loop readiness pass** (direct-to-main) — widened reviewer smoke gate to "any behavior change"; added Playwright mandate + env workaround + `followup.md` prune rule to implementer; added `/loop` mode issue-pickup rules to `CLAUDE.md`; kept `docs/loop.md` in sync; pointer from `tasks/todo.md` Phase 2 to the issue queue; ADRs 0006 / 0007 / 0008 filed retroactively.
- DX issue 26 / PR 45 — `e2e` CI job (postgres + redis services, host-side uvicorn + vite, cached chromium, failure artifacts). First-run green (6/6 specs, 5.6s). Not yet in branch-protection required checks.
- DX issue 43 / PR 44 — `smoke-tester` agent description trimmed 445 → 268 chars so it re-registers.
- DX issue 25 / PR 42 — compose-aware vite dev proxy (`VITE_API_PROXY_TARGET` env var).
- DX issue 40 / PR 41 — `docs/loop.md` quick-reference.
- DX issue 38 / PR 39 — fully autonomous loop: auto-merge on clean approve, nits are bugs, user-visible features require Playwright spec, smoke-fail routes to implementer.
- DX issue 33 / PR 37 — pinned ruff to 0.15.11 across pre-commit + CI + pyproject.
- DX issue 32 / PR 34 — reviewer `should-fix` is non-negotiable.
- DX issue 29 / PR 30 — autonomous pre-merge review loop codified.
- DX issue 24 / PR 27 — smoke-tester subagent + Playwright e2e baseline.

Full pre-Phase-2 history in `git log`.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens), 0006 (Playwright e2e + smoke-tester agent), 0007 (autonomous pre-merge review loop), 0008 (Playwright spec mandatory on every task).

**Convention reminder**: write bare issue references like "issue 23" in `followup.md` rather than `#23` — GitHub's keyword scanner interprets literal `#NN` in merge commits as closing references, which previously auto-closed issue 23 without a fix. PR bodies use `#N`; `followup.md` uses bare numbers.

## Next

1. **Loop auto-picks issue 69** (`feat(api): POST /api/boards` — create board). First Phase 2 REST endpoint. Consumes the `boards_service.create_board` skeleton now shipped. Expected loop: implementer → smoke-tester (Playwright `request` spec per issue body) → reviewer → auto-merge.

2. **After 69 closes, loop continues to issue 70** (`feat(api): GET /api/boards` — list boards). Read-path counterpart; consumes `list_boards` + `board_repo.list_active` already shipped.

3. **Then issue 71** (`feat(api): GET /api/boards/{id}` — board detail with embedded columns + labels). Hits `board_repo.get_by_id` + the column/label relationships defined on `Board`.

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
