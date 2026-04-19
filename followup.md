# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed (PR 137). Six Phase 2 REST endpoints shipped (issues 69-73 boards CRUD + archive, plus issue 77 — first columns endpoint). Three Phase 2 frontend issues landed (74 boards list, 75 create-board modal, 76 archive board UI)**. Issue 77 added `POST /api/boards/{board_id}/columns` — first endpoint on the columns surface. The route lives in a new `app/api/columns.py` module rather than nesting inside `app/api/boards.py`: column-related endpoints (the create here, plus #78 PATCH / #79 DELETE / #80 reorder coming next) cluster together, while the boards module stays focused on boards-only verbs. The router is mounted on the same `/api` prefix in `main_api.py`. Service in new `app/services/columns_service.py` owns the transaction per ADR-0001 and emits the same `BoardError("board_not_found")` already used by `boards_service.update_board`, so the router's 404 mapping is a one-liner exception handler. Position math: `MAX(position) + COLUMN_POSITION_STEP` (1000), or `1000` when the board has no columns. The model uses `Integer` (deliberate carve-out from ADR-0004's float-position scheme — column reorders are rare per the model docstring), so the issue body's `+ 1000.0` is satisfied by integer arithmetic with no precision loss. Repo gained `max_position_for_board(board_id) -> int | None` (`SELECT MAX(position) WHERE board_id = ?`) and a `create(...)` constructor. Archived boards 404 on column create (same model as the boards PATCH endpoint — archived = read-only, not 403, so probers can't tell archived-but-exists from never-existed). 9 pytest cases lock: happy path, second-column position math (1000 → 2000), optional `wip_limit`, unknown-board 404, archived-board 404, empty-name 422, oversized-name 422, `wip_limit=0` 422, no-auth 401. Mandatory Playwright smoke at `frontend/tests/e2e/api/columns.spec.ts` ships with two scenarios per the issue body: POST column on a fresh board → 201 with full `ColumnRead` shape (id, board_id, name, position=1000, wip_limit, created_at, updated_at), and POST on unknown board id (9999999) → 404. This is the first columns spec; issues 78/79/80 will extend the same file rather than fanning out per verb.

**Phase 2 issue queue continues**. With issue 77 closed, the loop continues with issue 78 (`feat(api): PATCH /api/columns/{id} — update column name/wip_limit`) which is the next lowest-open. Then 79 (DELETE column with `column_has_tasks` 409 protection), then 80 (column reorder), and the columns-CRUD chunk closes — loop moves to tasks endpoints.

Merged to `main` (recent — earlier history in `git log`):
- Issue 77 / PR (this) — `feat(api): POST /api/boards/{id}/columns`. New `app/api/columns.py` router, new `app/services/columns_service.py`, repo gains `max_position_for_board()` + `create()`. Position math `MAX(position) + 1000` (integer, model carve-out from ADR-0004). 9 pytest cases; new Playwright spec `frontend/tests/e2e/api/columns.spec.ts` (2 scenarios) — first columns spec, sets pattern for #78/#79/#80.
- Issue 76 / PR — `feat(frontend): archive board UI`. Per-row inline Archive button in `BoardsListView.vue`; new reusable `ConfirmDialog.vue` (focus trap + ESC + backdrop close + focus restore + `default`/`danger` variants); store `archive(id)` action with `archiving: number | null` flag; `archiveBoardApi(id)` wrapper. Six scenarios on `boards-list.spec.ts` (was three); second route regex `BOARDS_ARCHIVE_ROUTE` avoids widening the list regex. Three new vitest cases. Pre-merge review fix-up commit hardened ESC-busy guard, added nested-modal TODO, narrowed archive failures to component-local console.warn (not the page-level `boards.error` slot).
- Issue 75 / PR — `feat(frontend): create-board modal`. Reusable `CreateBoardModal.vue`, `createBoardApi` wrapper, store `create()` action with separate `creating` flag, "New board" header button + wired empty-state CTA. Three Playwright scenarios on `boards-list.spec.ts`.
- Issue 74 / PR — `feat(frontend): boards list view at /boards`. Route, store, view, types, api wrapper, vitest store sanity, page-driven Playwright spec covering empty-state CTA happy path. Sets the type+api+store+view+spec pattern.
- Issue 73 / PR — `POST /api/boards/{id}/archive`. Idempotent (preserves original timestamp on repeat), no cascade. 7 pytest cases.
- Issue 72 / PR — `PATCH /api/boards/{id}`. `exclude_unset` semantics for `null = clear`; archived = 404; `await session.refresh(board, ["updated_at"])` to avoid `MissingGreenlet` on response serialization.
- Issue 71 / PR — `GET /api/boards/{id}`. New `BoardDetailRead` schema with eager-loaded columns + labels via `selectinload`; ≤3 SELECTs locked by N+1 assertion.
- Issue 70 / PR 140 — `GET /api/boards`. `include_archived: bool = False` query param dispatching between `board_repo.list_active` and `board_repo.list_all`.
- Issue 69 / PR 139 — `POST /api/boards`. Router mounted under `/api`; commit owned by service per ADR-0001; `TODO(ws)` for Phase 3 Redis publish per ADR-0002.
- Issue 35 / PR 138 — pinned remaining backend dev-deps to exact `==` versions; CI mirrored.
- Issue 36 / PR 137 — Phase 2 data layer kickoff. Five models, migration with hand-authored `task_priority_enum.drop()` in downgrade, read-only repositories, stubbed services, domain schemas.
- Issue 68 / PR 136 — pre-push `main-branch-docs-only-guard` hook with allow-list (`docs/`, `thoughts/`, `tasks/`, repo-root `*.md`).
- Issue 67 / PR 135 — `backend/.env.local` override loaded after `.env`; canonical fix for the `postgres:5432` resolve trap.
- **DX pre-loop readiness pass** (direct-to-main) — widened reviewer smoke gate to "any behavior change"; added Playwright mandate + env workaround + `followup.md` prune rule to implementer; added `/loop` mode issue-pickup rules to `CLAUDE.md`; ADRs 0006 / 0007 / 0008 filed retroactively.

Full pre-Phase-2 history in `git log`.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens), 0006 (Playwright e2e + smoke-tester agent), 0007 (autonomous pre-merge review loop), 0008 (Playwright spec mandatory on every task).

**Convention reminder**: write bare issue references like "issue 23" in `followup.md` rather than `#23` — GitHub's keyword scanner interprets literal `#NN` in merge commits as closing references, which previously auto-closed issue 23 without a fix. PR bodies use `#N`; `followup.md` uses bare numbers.

## Next

1. **Loop auto-picks issue 78** — `feat(api): PATCH /api/columns/{id} — update column name/wip_limit`. Column id at root (not nested under board) — `board_id` resolved from DB. Acceptance: 200, 404, 422; 2+ pytest cases. Spec extends `columns.spec.ts`. Same `BoardError`-style 404 already wired into `app/api/columns.py`; service file `app/services/columns_service.py` exists from issue 77 and just needs an `update_column` function. Note: `ColumnUpdate` schema in `app/domain/columns.py` already supports `exclude_unset` semantics for `wip_limit: null` = clear (mirroring boards PATCH).

2. **After 78 closes, loop continues to issue 79** — `feat(api): DELETE /api/columns/{id} — delete column (protected if non-empty)`. 409 `{detail: 'column_has_tasks', task_count: N}` if column contains tasks; 204 on empty; 404 unknown. 3+ pytest cases. Spec extends `columns.spec.ts`. Will need a new `ColumnError` class in `columns_service.py` (the 409 isn't board-error-shaped).

3. **Then issue 80** — `feat(api): POST /api/boards/{id}/columns/reorder` (or whatever the issue body specifies — re-read on pickup). Closes the columns-CRUD chunk; loop moves to tasks endpoints (#81+).

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Add a global toast/notification system once 2-3 flows need it (deferred from issue 75 — currently only one flow uses inline errors).
   - "Show archived" toggle on boards list view — deferred from issue 76; lands when board-restore UI ships or when bot/web sync needs to surface archived boards.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
