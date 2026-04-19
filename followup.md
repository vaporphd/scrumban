# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed (PR 137). Five Phase 2 REST endpoints shipped (issues 69-73 — boards CRUD + archive). Three Phase 2 frontend issues now landed: 74 (boards list view), 75 (create-board modal), 76 (archive board UI)**. Issue 76 added per-row inline "Archive" buttons in `BoardsListView.vue` (kebab menu deferred — single-action rows make a button cleaner) plus a new reusable `ConfirmDialog.vue` component. The dialog mirrors `CreateBoardModal.vue`'s focus-trap + ESC + backdrop + focus-restore pattern; the focus-trap stayed inline (~15 lines) rather than extracting to a `useFocusTrap` composable — two callers is below the extract threshold, the third caller (likely #79's column-delete confirm) is when we'd refactor. ConfirmDialog props: `title`, `body`, `confirmLabel`, `cancelLabel`, `confirmVariant: 'default' | 'danger'`, `busy`, `testidPrefix`. Boards store gained `archive(id)` action with `archiving: number | null` flag (per-row spinner state, not boolean) and `archiveBoardApi(id)` wrapper hitting `POST /api/boards/{id}/archive`. The default `GET /api/boards` excludes archived rows (issue 70) so re-fetch on success removes the row from the list automatically — no client-side splice. "Show archived" toggle is intentionally deferred per issue 76's "optional" marker; will land alongside board-restore or when bot/web sync needs it. Mandatory Playwright smoke extends `boards-list.spec.ts` from three to five scenarios: archive happy-path (row → Archive button → Confirm → row gone, empty-state CTA visible) and ESC-cancel (row → Archive button → ESC → row stays, no POST fires). Spec adds a second route regex `BOARDS_ARCHIVE_ROUTE = /\/api\/boards\/\d+\/archive$/` rather than widening the existing `BOARDS_ROUTE` — keeps each handler's intent narrow and avoids accidentally swallowing future sub-resources like `/api/boards/{id}/columns` from issue 77. Three new vitest cases for the store cover happy-path (POST then auto-refresh, archived row excluded), in-flight `archiving` flag, and rejection (404 with `detail` propagates as `ApiError`, `archiving` clears, `error` set, no refresh fires).

**Phase 2 issue queue continues**. With issue 76 closed, the loop shifts back to backend mode: issue 77 (`feat(api): POST /api/boards/{id}/columns — create column`) is the next lowest-open. After that the loop continues with issue 78 (PATCH column) and 79 (DELETE column with `column_has_tasks` 409 protection) — all backend `feat(api)` issues with mandatory api-context Playwright specs under `frontend/tests/e2e/api/columns.spec.ts`.

Merged to `main` (recent — earlier history in `git log`):
- Issue 76 / PR (this) — `feat(frontend): archive board UI`. Per-row inline Archive button in `BoardsListView.vue`; new reusable `ConfirmDialog.vue` (focus trap + ESC + backdrop close + focus restore + `default`/`danger` variants); store `archive(id)` action with `archiving: number | null` flag; `archiveBoardApi(id)` wrapper. Five scenarios on `boards-list.spec.ts` (was three) — archive happy-path + ESC cancel; second route regex `BOARDS_ARCHIVE_ROUTE` avoids widening the list regex. Three new vitest cases. "Show archived" toggle deferred (issue 76 says optional).
- Issue 75 / PR — `feat(frontend): create-board modal`. Reusable `CreateBoardModal.vue`, `createBoardApi` wrapper, store `create()` action with separate `creating` flag, "New board" header button + wired empty-state CTA. Three Playwright scenarios on `boards-list.spec.ts` covering both entry points + ESC cancel + validation + happy path.
- Issue 74 / PR — `feat(frontend): boards list view at /boards`. Route, store, view, types, api wrapper, vitest store sanity, page-driven Playwright spec covering the empty-state CTA happy path. First frontend Phase 2 issue; sets the type+api+store+view+spec pattern that issues 75-77 reuse.
- Issue 73 / PR — `POST /api/boards/{id}/archive`. Idempotent (preserves original timestamp on repeat), no cascade. 7 pytest cases; Playwright spec extended from 7 to 8 scenarios (picks up the deferred `TODO(#73)` from PR 140).
- Issue 72 / PR — `PATCH /api/boards/{id}`. `exclude_unset` semantics for `null = clear`; archived = 404; critical fix `await session.refresh(board, ["updated_at"])` to avoid `MissingGreenlet` on response serialization.
- Issue 71 / PR — `GET /api/boards/{id}`. New `BoardDetailRead` schema with eager-loaded columns + labels via `selectinload`; ≤3 SELECTs locked by N+1 assertion.
- Issue 70 / PR 140 — `GET /api/boards`. `include_archived: bool = False` query param dispatching between `board_repo.list_active` and `board_repo.list_all`.
- Issue 69 / PR 139 — `POST /api/boards`. Router mounted under `/api`; commit owned by service per ADR-0001; `TODO(ws)` left for Phase 3 Redis publish per ADR-0002.
- Issue 35 / PR 138 — pinned remaining backend dev-deps to exact `==` versions; CI mirrored.
- Issue 36 / PR 137 — Phase 2 data layer kickoff. Five models, migration with hand-authored `task_priority_enum.drop()` in downgrade, read-only repositories, stubbed services, domain schemas.
- Issue 68 / PR 136 — pre-push `main-branch-docs-only-guard` hook with allow-list (`docs/`, `thoughts/`, `tasks/`, repo-root `*.md`).
- Issue 67 / PR 135 — `backend/.env.local` override loaded after `.env`; canonical fix for the `postgres:5432` resolve trap.
- **DX pre-loop readiness pass** (direct-to-main) — widened reviewer smoke gate to "any behavior change"; added Playwright mandate + env workaround + `followup.md` prune rule to implementer; added `/loop` mode issue-pickup rules to `CLAUDE.md`; ADRs 0006 / 0007 / 0008 filed retroactively.

Full pre-Phase-2 history in `git log`.

ADRs in force: 0001 (api+bot split with shared services), 0002 (Redis pub/sub realtime bus), 0003 (Telegram linking via one-time code), 0004 (float position for task ordering), 0005 (opaque rotating refresh tokens), 0006 (Playwright e2e + smoke-tester agent), 0007 (autonomous pre-merge review loop), 0008 (Playwright spec mandatory on every task).

**Convention reminder**: write bare issue references like "issue 23" in `followup.md` rather than `#23` — GitHub's keyword scanner interprets literal `#NN` in merge commits as closing references, which previously auto-closed issue 23 without a fix. PR bodies use `#N`; `followup.md` uses bare numbers.

## Next

1. **Loop auto-picks issue 77** — `feat(api): POST /api/boards/{id}/columns — create column`. Body: `name` + optional `wip_limit`. Position = `max(position) + 1000.0`. Acceptance: 201 with `ColumnRead`, 404 on unknown board, 3+ pytest cases. Mandatory api-context Playwright spec at `frontend/tests/e2e/api/columns.spec.ts` — first columns spec, sets the pattern that 78 + 79 will extend.

2. **After 77 closes, loop continues to issue 78** — `feat(api): PATCH /api/columns/{id} — update column name/wip_limit`. Column id at root (not nested under board) — `board_id` resolved from DB. Acceptance: 200, 404, 422; 2+ pytest cases. Spec extends `columns.spec.ts`.

3. **Then issue 79** — `feat(api): DELETE /api/columns/{id} — delete column (protected if non-empty)`. 409 `{detail: 'column_has_tasks', task_count: N}` if column contains tasks; 204 on empty; 404 unknown. 3+ pytest cases. Spec extends `columns.spec.ts`. After this, the columns-CRUD chunk closes and the loop moves to columns-reorder + then tasks endpoints.

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Add a global toast/notification system once 2-3 flows need it (deferred from issue 75 — currently only one flow uses inline errors).
   - "Show archived" toggle on boards list view — deferred from issue 76; lands when board-restore UI ships or when bot/web sync needs to surface archived boards.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
