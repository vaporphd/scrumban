// Spec: boards list view (issues #74 + #75) — first frontend Phase 2 view.
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
// Subsequent issues (#76 detail view) will extend this spec with list /
// navigate scenarios.
//
// Route glob: we match `/api/boards` and `/api/boards?…anything`. A bare
// `**/api/boards` glob would silently miss future querystring requests
// (e.g. `?include_archived=true` in #80), so we use a regex that anchors on
// the path and accepts an optional query string. This keeps the intercept
// "everything that hits the boards list endpoint" rather than "the exact URL
// the current PR happens to use."
import { expect, test, type Route } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

const BOARDS_ROUTE = /\/api\/boards(\?|$)/

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
