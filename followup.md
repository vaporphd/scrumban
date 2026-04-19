# Followup

## Status

Branch `main`, in sync with `origin/main`. **Phase 0 complete. Phase 1 complete end-to-end. Phase 2 data layer landed (PR 137). Five Phase 2 REST endpoints shipped (issues 69-73 — boards CRUD + archive). First Phase 2 frontend issue now landed: issue 74 — `feat(frontend): boards list view at /boards`**. New route `/boards` (auth-guarded, mirrors `/profile`'s guard) renders four states off a fresh `useBoardsStore` Pinia options-store: loading spinner, error message + retry button, empty-state CTA "Create your first board" (button is a stub — issue 75 wires it to a modal), and a `<ul>` of `<router-link>`s to `/boards/{id}` (the detail route doesn't exist yet — links 404 on click until that ships, by design). New files: `frontend/src/types/boards.ts` (mirrors `BoardRead`), `frontend/src/api/boards.ts` (`listBoardsApi()` over the shared `http()` client — JWT bearer + 401 silent-refresh inherited for free), `frontend/src/stores/boards.ts` (options-store matching `auth.ts` style with `boards`, `loading`, `error` and a `list()` action; surfaces `ApiError.detail` like the auth store does), `frontend/src/views/BoardsListView.vue` (the view — `data-testid="create-first-board-cta"` and `data-testid="boards-retry"` exposed for smoke selectors). Router gains a `requiresAuth: true` `/boards` route; `App.vue` nav gains a "Boards" link visible only when authenticated. Two vitest cases for the store (`boards.spec.ts` mirrors `auth.spec.ts` — happy path populates `boards` + clears state; 500 captures `detail`). Mandatory Playwright spec `frontend/tests/e2e/boards-list.spec.ts` (page-driven, not request-context) registers a fresh user → navigates to `/boards` → asserts the empty-state CTA is visible and reads "Create your first board". Pattern set for the rest of the Phase 2 frontend stack: types under `src/types/<resource>.ts` mirroring backend domain schemas, thin api wrappers under `src/api/<resource>.ts` using the shared `http()` client, options-store with `loading` / `error` / data fields and `ApiError.detail`-aware error messages, view components reading store state via `onMounted` + `void store.action()`, page-driven Playwright specs for each user-visible affordance.

**Phase 2 issue queue continues**. With issue 74 closed, the loop auto-picks issue 75 (`feat(frontend): create-board modal`) — wires `POST /api/boards` (issue 69) from a UI affordance and replaces the empty-state CTA stub button with a real modal trigger.

Merged to `main` (recent — earlier history in `git log`):
- Issue 74 / PR (this) — `feat(frontend): boards list view at /boards`. Route, store, view, types, api wrapper, vitest store sanity, page-driven Playwright spec covering the empty-state CTA happy path. First frontend Phase 2 issue; sets the type+api+store+view+spec pattern that issues 75-77 will reuse.
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

1. **Loop auto-picks issue 75** (`feat(frontend): create-board modal`) — wires `POST /api/boards` (issue 69) from a UI affordance, replacing the stub empty-state CTA button with a real modal trigger. Page-context Playwright spec extends `boards-list.spec.ts` (or a new `create-board.spec.ts`) with: open modal → fill form → submit → assert new board appears in list and modal closes.

2. **After 75 closes, loop continues to issue 76** — next Phase 2 frontend issue (likely board-detail view consuming `GET /api/boards/{id}` from issue 71 or board-archive UI consuming `POST /api/boards/{id}/archive` from issue 73 — verify with `gh issue view 76`). Page-context Playwright spec.

3. **Then issue 77** — next in the Phase 2 frontend queue. Likely closes out the boards-frontend chunk, after which the loop moves to columns endpoints (todo.md line 167 — `/api/boards/{id}/columns` CRUD + reorder).

4. **Deferred user actions** (none gate the loop):
   - Flip `e2e` CI job to branch-protection required check after 2-3 more green runs: `gh api -X PATCH repos/vaporphd/scrumban/branches/main/protection/required_status_checks -F 'strict=true' -f 'contexts[]=backend' -f 'contexts[]=frontend' -f 'contexts[]=e2e'`.
   - Consider a server-side equivalent of the docs-only guard — a GitHub ruleset or stricter branch protection — since `--no-verify` bypasses the client hook. Low priority while Alex is solo admin.
   - Consider an architectural-review checkpoint after each Tier completion (~5-10 PRs) if cross-PR drift becomes a concern.
