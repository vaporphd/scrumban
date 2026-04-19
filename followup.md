# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed (PR 137). Five Phase 2 REST endpoints shipped (issues 69-73 — boards CRUD + archive). Two Phase 2 frontend issues now landed: issue 74 — `feat(frontend): boards list view at /boards` and issue 75 — `feat(frontend): create-board modal`**. The boards list view at `/boards` (auth-guarded, mirrors `/profile`'s guard) renders four states off `useBoardsStore`: loading spinner, error+retry, empty-state CTA, and a list of `<router-link>`s to `/boards/{id}`. Issue 75 added a reusable `CreateBoardModal.vue` (focus on mount, ESC + backdrop close, inline name-required validation, inline submit-error on POST failure, `creating` flag to gate the submit button) plus a new "New board" header button visible whenever the user is on `/boards`. Both the header button and the empty-state CTA flip the same `isModalOpen` ref in `BoardsListView.vue` — a single owner of modal lifecycle, no store-level toggle. The previously-disabled empty-state CTA stub from issue 74 is now wired (the `disabled` + `title="Coming soon"` attributes are gone). The boards store gained a `create(payload)` action (separate `creating` flag from list-`loading`) that POSTs via the new `createBoardApi` wrapper, then re-fetches the list on success so server-owned ordering / archived-filter logic stays canonical. Mandatory Playwright smoke extends `boards-list.spec.ts` from one to three scenarios (empty-state CTA still passes; new: empty-state CTA → fill modal → submit → board appears in list, header button → ESC cancels). Tests use `page.route()` mocking both POST and GET on `/api/boards` per the precedent locked in by reviewer on PR 144 — deterministic and fast, no DB writes from the page spec. Two new vitest cases for the store cover happy-path (POST then auto-refresh) and rejection (422 with `detail` propagates as `ApiError`, `creating` flag clears, no refresh fires). Inline error messages chosen over a global toast system — noted in PR body as a deliberate scope deferral. Pattern locked in for future modal work (issue 76+): single `is*ModalOpen` ref in the parent view, separate store-level loading flags per action so concurrent flows don't fight each other.

**Phase 2 issue queue continues**. With issue 75 closed, the loop auto-picks issue 76 — verify with `gh issue view 76` for scope (likely board-detail view consuming `GET /api/boards/{id}` from issue 71 or board-rename/edit UI consuming `PATCH /api/boards/{id}` from issue 72).

Merged to `main` (recent — earlier history in `git log`):
- Issue 75 / PR (this) — `feat(frontend): create-board modal`. Reusable `CreateBoardModal.vue`, `createBoardApi` wrapper, store `create()` action with separate `creating` flag, "New board" header button + wired empty-state CTA. Three Playwright scenarios on `boards-list.spec.ts` covering both entry points + ESC cancel + validation + happy path.
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

1. **Loop auto-picks issue 76** — next Phase 2 frontend issue. Verify with `gh issue view 76` for exact scope (likely board-detail view consuming `GET /api/boards/{id}` from issue 71, or board edit/rename UI consuming `PATCH /api/boards/{id}` from issue 72). Page-context Playwright spec extends or adds a new spec under `frontend/tests/e2e/`.

2. **After 76 closes, loop continues to issue 77** — next in the Phase 2 frontend queue. Likely board-archive UI consuming `POST /api/boards/{id}/archive` (issue 73) — closes out the boards-frontend chunk, after which the loop moves to columns endpoints (todo.md line 167 — `/api/boards/{id}/columns` CRUD + reorder).

3. **Then issue 78** — first columns-CRUD endpoint (likely `POST /api/boards/{id}/columns`). Switches the loop back to backend mode. Mandatory api-context Playwright spec under `frontend/tests/e2e/api/columns.spec.ts`.

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Add a global toast/notification system once 2-3 flows need it (deferred from issue 75 — currently only one flow uses inline errors).
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
