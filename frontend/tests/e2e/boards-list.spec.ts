// Spec: boards list view (issues #74 + #75 + #76) — frontend Phase 2 view.
//
// Page-driven (not request context — this is UI). Mints a fresh user via the
// existing register helper, then intercepts `/api/boards` to force a
// deterministic response so each scenario has a known starting state.
//
// Why network interception (not "rely on a fresh user having no boards"):
// the `GET /api/boards` endpoint is **not user-scoped** yet (RBAC is Phase 7,
// see backend/app/services/boards_service.py:list_boards docstring). A
// freshly-registered user sees every board the parallel API-spec workers in
// `frontend/tests/e2e/api/boards.spec.ts` are creating concurrently in the
// same DB, so an unmocked spec is non-deterministic under CI load.
// Intercepting the response keeps this spec focused on the **frontend's**
// rendering — backend list/create semantics are already covered by backend
// pytest + the api-context boards spec.
//
// Route regexes — issue #76 added the archive flow, which hits a nested path
// (`/api/boards/{id}/archive`) that the original `BOARDS_ROUTE` regex
// (`/api/boards(\?|$)/`) intentionally does NOT match (it anchors on the
// list endpoint only — see PR #145). Rather than widen `BOARDS_ROUTE` to
// match every nested path (and accidentally swallow future sub-resources
// like `/api/boards/{id}/columns` when those land in #77), we add a second
// dedicated regex `BOARDS_ARCHIVE_ROUTE` that matches only the archive
// endpoint. Two narrow regexes registered as two `page.route(...)` handlers
// keep each handler's intent obvious.
import { expect, test, type Route } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

const BOARDS_ROUTE = /\/api\/boards(\?|$)/
const BOARDS_ARCHIVE_ROUTE = /\/api\/boards\/\d+\/archive$/

test('register → /boards → empty-state CTA visible', async ({ page }) => {
  const username = randomUsername('boards_list')
  const displayName = `Boards List Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Force the boards-list response to empty so we always land on the
  // empty-state CTA branch (see file-level docstring).
  await page.route(BOARDS_ROUTE, async (route, request) => {
    if (request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
      return
    }
    await route.continue()
  })

  await page.goto('/boards')

  // Scope to <main> — the navbar also has a "Boards" link, which would
  // collide with a global getByText in strict mode.
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Boards' })).toBeVisible()
  await expect(page.getByTestId('create-first-board-cta')).toBeVisible()
  await expect(page.getByTestId('create-first-board-cta')).toHaveText(
    /Create your first board/,
  )
})

test('create-board modal: empty-state CTA → fill form → submit → board appears', async ({
  page,
}) => {
  const username = randomUsername('boards_create')
  const displayName = `Boards Create Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Mock both verbs against the same path. We start with an empty list so the
  // empty-state CTA renders. POST returns the created board; the next GET
  // (refresh after success) returns [createdBoard], which the view should
  // render as a single list item.
  let listResponse: unknown[] = []
  await page.route(BOARDS_ROUTE, async (route: Route) => {
    const req = route.request()
    if (req.method() === 'POST') {
      const body = JSON.parse(req.postData() ?? '{}') as {
        name: string
        description: string | null
      }
      const created = {
        id: 1,
        name: body.name,
        description: body.description,
        created_by: 1,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T10:00:00Z',
        archived_at: null,
      }
      listResponse = [created]
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(created),
      })
      return
    }
    if (req.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(listResponse),
      })
      return
    }
    await route.continue()
  })

  await page.goto('/boards')

  // Open from the empty-state CTA (not the header button) — the issue body
  // calls out wiring this entry point as part of #75.
  await page.getByTestId('create-first-board-cta').click()

  const modal = page.getByTestId('create-board-modal')
  await expect(modal).toBeVisible()

  // Submit-empty-name path: server is never hit; inline validation message shows.
  await page.getByTestId('create-board-submit').click()
  await expect(page.getByTestId('create-board-validation-error')).toBeVisible()

  // Happy path.
  await page.getByTestId('create-board-name-input').fill('My first board')
  await page.getByTestId('create-board-description-input').fill('Sandbox')
  await page.getByTestId('create-board-submit').click()

  // Modal closes after success and the new board renders in the list.
  await expect(modal).toBeHidden()
  const list = page.getByTestId('boards-list')
  await expect(list.getByText('My first board')).toBeVisible()
  await expect(list.getByText('Sandbox')).toBeVisible()
})

test('create-board modal: header button is also an entry point + ESC cancels', async ({
  page,
}) => {
  const username = randomUsername('boards_header_modal')
  const displayName = `Boards Header Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Empty list — we want the header button to be reachable from the
  // empty-state branch too (the issue spec says the header button is
  // visible always, not only when boards.length > 0).
  await page.route(BOARDS_ROUTE, async (route, request) => {
    if (request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
      return
    }
    await route.continue()
  })

  await page.goto('/boards')

  await page.getByTestId('open-create-board-modal').click()
  const modal = page.getByTestId('create-board-modal')
  await expect(modal).toBeVisible()

  // ESC cancels — modal disappears, no POST fires.
  await page.keyboard.press('Escape')
  await expect(modal).toBeHidden()
})

test('archive board: confirm dialog → row disappears from default list', async ({
  page,
}) => {
  // Mandatory smoke for issue #76. Asserts the full archive flow:
  //   list shows board → click row Archive → ConfirmDialog → click Confirm →
  //   archive POST fires → list re-fetches → row no longer rendered.
  //
  // Backend behavior we lean on (issue #73): POST /api/boards/{id}/archive is
  // idempotent and returns 200 with the archived board (including its
  // `archived_at` timestamp). The default GET /api/boards excludes archived
  // rows (issue #70 — `include_archived=False`). We mirror both behaviors in
  // the route mocks below: POST flips `archived_at` on the in-memory record;
  // GET filters it out.
  const username = randomUsername('boards_archive')
  const displayName = `Boards Archive Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Mutable list: starts with one visible board. Archive flips its
  // `archived_at` to a non-null timestamp; the next GET filters it out.
  type MockBoard = {
    id: number
    name: string
    description: string | null
    created_by: number
    created_at: string
    updated_at: string
    archived_at: string | null
  }
  const allBoards: MockBoard[] = [
    {
      id: 1,
      name: 'Sandbox',
      description: 'to be archived',
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
    },
  ]

  // Handler 1: list endpoint (GET-only here — POST/create is not exercised in
  // this scenario, so we don't bother reusing the create-board branch from
  // the earlier test).
  await page.route(BOARDS_ROUTE, async (route: Route) => {
    if (route.request().method() === 'GET') {
      const visible = allBoards.filter((b) => b.archived_at === null)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(visible),
      })
      return
    }
    await route.continue()
  })

  // Handler 2: archive endpoint. Idempotent — first call flips archived_at,
  // subsequent calls leave it untouched. The 2026-04-19 timestamp matches
  // the rest of this spec for consistency.
  await page.route(BOARDS_ARCHIVE_ROUTE, async (route: Route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    const url = new URL(route.request().url())
    const match = url.pathname.match(/\/api\/boards\/(\d+)\/archive$/)
    const id = match ? Number(match[1]) : NaN
    const target = allBoards.find((b) => b.id === id)
    if (!target) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'board_not_found' }),
      })
      return
    }
    if (target.archived_at === null) {
      target.archived_at = '2026-04-19T11:00:00Z'
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(target),
    })
  })

  await page.goto('/boards')

  // The seeded board renders.
  const list = page.getByTestId('boards-list')
  await expect(list.getByText('Sandbox')).toBeVisible()

  // Open the confirm dialog from the row's Archive button.
  await page.getByTestId('board-row-archive-1').click()
  const dialog = page.getByTestId('archive-board-confirm')
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('Archive this board?')
  await expect(dialog).toContainText("'Sandbox' will be hidden")

  // Confirm — backend archives, store re-fetches, row disappears, dialog closes.
  await page.getByTestId('archive-board-confirm-confirm').click()

  await expect(dialog).toBeHidden()
  // The list either has the row removed or the whole list is replaced by the
  // empty-state CTA (since this scenario starts with a single board). We
  // assert both: 'Sandbox' must be gone, AND the empty-state CTA renders.
  await expect(page.getByText('Sandbox')).toBeHidden()
  await expect(page.getByTestId('create-first-board-cta')).toBeVisible()
})

test('archive board: ESC on confirm dialog cancels (no archive POST fires)', async ({
  page,
}) => {
  // Companion scenario to the happy-path archive test above: the user opens
  // the confirm dialog and presses ESC. The board must remain in the list
  // and no POST may fire. Mirrors the create-modal ESC test for consistency.
  const username = randomUsername('boards_archive_esc')
  const displayName = `Boards Archive ESC ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  let archiveCalls = 0

  await page.route(BOARDS_ROUTE, async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 5,
            name: 'StaysHere',
            description: null,
            created_by: 7,
            created_at: '2026-04-19T10:00:00Z',
            updated_at: '2026-04-19T10:00:00Z',
            archived_at: null,
          },
        ]),
      })
      return
    }
    await route.continue()
  })

  await page.route(BOARDS_ARCHIVE_ROUTE, async (route: Route) => {
    archiveCalls += 1
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'this should not have been called' }),
    })
  })

  await page.goto('/boards')

  await page.getByTestId('board-row-archive-5').click()
  const dialog = page.getByTestId('archive-board-confirm')
  await expect(dialog).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(page.getByText('StaysHere')).toBeVisible()
  expect(archiveCalls).toBe(0)
})

test('archive board: ESC is ignored while the archive POST is in flight (busy-guard)', async ({
  page,
}) => {
  // Reviewer finding on PR #146: ConfirmDialog.vue documented that `busy`
  // disables "both buttons + ESC + backdrop", but the Escape branch in
  // onKeydown emitted `cancel` unconditionally. Now gated on `props.busy`.
  // This spec pins the new behavior: while archive is in flight the dialog
  // stays open, the row stays, and a stray ESC does not close the dialog.
  // We deliberately hold the POST open until after pressing ESC, then
  // resolve it and assert the dialog closes naturally on success.
  const username = randomUsername('boards_archive_busy_esc')
  const displayName = `Boards Archive Busy ESC ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Mutable "DB" so the post-archive refresh GET reflects the archived row
  // disappearing. Same pattern as the happy-path archive scenario above.
  type MockBoard = {
    id: number
    name: string
    description: string | null
    created_by: number
    created_at: string
    updated_at: string
    archived_at: string | null
  }
  const allBoards: MockBoard[] = [
    {
      id: 9,
      name: 'BusyBoard',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
    },
  ]

  await page.route(BOARDS_ROUTE, async (route: Route) => {
    if (route.request().method() === 'GET') {
      const visible = allBoards.filter((b) => b.archived_at === null)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(visible),
      })
      return
    }
    await route.continue()
  })

  // Hold the archive POST open via a deferred promise so we have a window
  // in which `busy === true` and can press ESC to assert the gate fires.
  // The test itself resolves the promise once the assertion is complete.
  let resolvePost!: () => void
  const postHeld = new Promise<void>((resolve) => {
    resolvePost = resolve
  })

  await page.route(BOARDS_ARCHIVE_ROUTE, async (route: Route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await postHeld
    const target = allBoards.find((b) => b.id === 9)!
    target.archived_at = '2026-04-19T11:00:00Z'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(target),
    })
  })

  await page.goto('/boards')

  await page.getByTestId('board-row-archive-9').click()
  const dialog = page.getByTestId('archive-board-confirm')
  await expect(dialog).toBeVisible()

  // Click confirm — POST is held open by `postHeld`, so the dialog enters
  // the busy state and the confirm button shows "Working…".
  await page.getByTestId('archive-board-confirm-confirm').click()
  const confirmBtn = page.getByTestId('archive-board-confirm-confirm')
  await expect(confirmBtn).toHaveText(/Working/)
  await expect(confirmBtn).toBeDisabled()

  // ESC must NOT close the dialog while busy.
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()

  // Now release the POST. The list refresh fires (which our handler
  // returns []), the row disappears, and the dialog closes.
  resolvePost()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('BusyBoard')).toBeHidden()
})
