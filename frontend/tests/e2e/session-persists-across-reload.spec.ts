// Spec #4: register → /profile → reload → still on /profile.
// Locks bootstrap() → /api/me cold-load + the router guard awaiting
// `auth.bootstrapPromise` before evaluating requiresAuth.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('session survives a hard reload without bouncing through /login', async ({ page }) => {
  const username = randomUsername('reload')
  const displayName = `Reload Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, password, displayName })

  await page.goto('/profile')
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Profile' })).toBeVisible()
  await expect(main.getByText(username, { exact: true })).toBeVisible()

  await page.reload()

  // If the bootstrapPromise wiring breaks, the guard will fire before /api/me
  // resolves and we'll bounce to /login here. That bounce is the failure mode
  // this spec exists to catch — assert URL stays put and Profile re-renders.
  await expect(page).toHaveURL(/\/profile$/)
  await expect(main.getByRole('heading', { name: 'Profile' })).toBeVisible()
  await expect(main.getByText(username, { exact: true })).toBeVisible()
})
