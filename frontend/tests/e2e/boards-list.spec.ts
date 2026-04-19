// Spec: boards list view (issue #74) — first frontend Phase 2 view.
//
// Page-driven (not request context — this is UI). Mints a fresh user via the
// existing register helper, then intercepts `GET /api/boards` to force a
// deterministic empty response so the empty-state CTA is the assertable
// landing.
//
// Why network interception (not "rely on a fresh user having no boards"):
// the `GET /api/boards` endpoint is **not user-scoped** yet (RBAC is Phase 7,
// see backend/app/services/boards_service.py:list_boards docstring). A
// freshly-registered user sees every board the parallel API-spec workers in
// `frontend/tests/e2e/api/boards.spec.ts` are creating concurrently in the
// same DB, so an unmocked spec is non-deterministic under CI load.
// Intercepting the response keeps this spec focused on the **frontend's**
// empty-state rendering — backend list semantics are already covered by
// backend pytest + the api-context boards spec.
//
// Subsequent issues (#75 create-board modal, #76 detail view) will extend
// this spec with create / list / navigate scenarios.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('register → /boards → empty-state CTA visible', async ({ page }) => {
  const username = randomUsername('boards_list')
  const displayName = `Boards List Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // Force the boards-list response to empty so we always land on the
  // empty-state CTA branch (see file-level docstring).
  await page.route('**/api/boards', async (route, request) => {
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
