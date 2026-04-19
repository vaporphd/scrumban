# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed (PR 137). Seven Phase 2 REST endpoints shipped (issues 69-73 boards CRUD + archive, plus 77 + 78 — first two columns endpoints). Three Phase 2 frontend issues landed (74 boards list, 75 create-board modal, 76 archive board UI)**. Issue 78 added `PATCH /api/columns/{column_id}` — partial update of `name` and/or `wip_limit`. Endpoint uses the **flat shape** `/columns/{column_id}` (id at root, board resolved from DB) — that's the pattern the next two columns endpoints (#79 DELETE, #80 reorder) will follow too. The columns router docstring now describes both shapes (sub-resource for create, flat for per-column verbs). Service introduces a new `ColumnError` class in `app/services/columns_service.py` (sibling of `BoardError`) — currently only carries `column_not_found` (404), but #79 will extend it with `column_has_tasks` (409) without churning the routing layer. Service mirrors the boards PATCH pattern: `model_dump(exclude_unset=True)` so explicit `wip_limit: null` clears, omitting leaves alone; `await session.refresh(column, ["updated_at"])` after flush to dodge the `MissingGreenlet` lazy-load trap (PR 142's lesson). Archived parent board surfaces as `BoardError("board_not_found")` → 404 (security-by-obscurity — same model as the boards PATCH endpoint). Repo gains `apply_updates(column, fields)` mirroring `board_repo.apply_updates`. 12 pytest cases lock: name-only, wip_limit-only, both, null-clear, no-op, two name-422 shapes, two wip_limit-422 shapes, unknown-id 404, archived-board 404, no-auth 401. Mandatory Playwright spec extends `frontend/tests/e2e/api/columns.spec.ts` (now 4 scenarios — was 2): PATCH renames a column → GET parent board reflects the new name in its embedded `columns[]` (the cross-endpoint contract the issue calls for, plus a wip_limit clear in the same call); PATCH on unknown column id → 404.

**Phase 2 issue queue continues**. With 78 closed, the loop continues with issue 79 (`feat(api): DELETE /api/columns/{id} — delete column (protected if non-empty)`) which is the next lowest-open. Then 80 (column reorder), then 81 (frontend column rendering on board detail route) — at which point the columns surface is feature-complete and the loop moves to tasks endpoints.

Merged to `main` (recent — earlier history in `git log`):
- Issue 78 / PR (this) — `feat(api): PATCH /api/columns/{id}`. New `update_column` service + flat-shape route at `/api/columns/{column_id}`. Introduces `ColumnError` class in `columns_service.py` (sibling of `BoardError`; today only `column_not_found`, room for #79's `column_has_tasks`). Repo gains `apply_updates`. `exclude_unset` clear semantics + `refresh(["updated_at"])` MissingGreenlet trap fix. Archived parent board → 404 obscurity contract. 12 pytest cases. Spec `frontend/tests/e2e/api/columns.spec.ts` extended to 4 scenarios — adds PATCH-then-GET-board cross-endpoint check + PATCH-unknown 404.
- Issue 77 / PR — `feat(api): POST /api/boards/{id}/columns`. New `app/api/columns.py` router, new `app/services/columns_service.py`, repo gains `max_position_for_board()` + `create()`. Position math `MAX(position) + 1000` (integer, model carve-out from ADR-0004). 9 pytest cases; new Playwright spec `frontend/tests/e2e/api/columns.spec.ts` (2 scenarios) — first columns spec.
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

1. **Loop auto-picks issue 79** — `feat(api): DELETE /api/columns/{id} — delete column (protected if non-empty)`. Flat shape `/api/columns/{column_id}` (matches #78). 204 on empty column; 409 `{detail: 'column_has_tasks', task_count: N}` if column contains tasks; 404 unknown id; 404 column on archived board (same obscurity contract). The new `ColumnError` class added in #78 already has room for the `column_has_tasks` code — service raises, router maps to 409. 3+ pytest cases. Spec extends `columns.spec.ts` (will be 6+ scenarios after).

2. **After 79 closes, loop continues to issue 80** — `feat(api): POST /api/boards/{id}/columns/reorder — reorder columns`. Closes the columns-CRUD backend chunk; loop then moves to frontend (#81).

3. **Then issue 81** — `feat(frontend): render columns on board detail route`. First UI surface that consumes the columns endpoints (`BoardDetailRead.columns[]`). Sets the rendering pattern that #82+ task-card UI will build on.

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Add a global toast/notification system once 2-3 flows need it (deferred from issue 75 — currently only one flow uses inline errors).
   - "Show archived" toggle on boards list view — deferred from issue 76; lands when board-restore UI ships or when bot/web sync needs to surface archived boards.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
