// Spec #1: register → auto-login → /profile shows user → token persisted.
// Locks the happy path of RegisterView + auth store + ProfileView from PR #21.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('register lands the user authenticated and /profile renders their details', async ({ page }) => {
  const username = randomUsername('reg')
  const displayName = `Register Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // RegisterView pushes / on success — but the home view content is not the focus
  // of this spec; we just need to be off /register and authenticated.
  expect(new URL(page.url()).pathname).not.toBe('/register')

  await page.goto('/profile')
  // Scope assertions to <main> — the navbar also renders the username as a link
  // when auth.isAuthenticated, which would break a global getByText with strict mode.
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Profile' })).toBeVisible()
  await expect(main.getByText(username, { exact: true })).toBeVisible()
  await expect(main.getByText(displayName, { exact: true })).toBeVisible()

  const access = await page.evaluate(() => localStorage.getItem('access_token'))
  expect(access).not.toBeNull()
  expect(access).not.toBe('')
})
