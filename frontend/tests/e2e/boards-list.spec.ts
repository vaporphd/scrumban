// Spec: boards list view (issue #74) — first frontend Phase 2 view.
//
// Page-driven (not request context — this is UI). Mints a fresh user via the
// existing register helper so a freshly-registered account has zero boards
// and the empty-state CTA is the deterministic landing.
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

  // Navigate to /boards directly. A freshly-registered user has no boards,
  // so the empty-state CTA is the expected landing.
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
