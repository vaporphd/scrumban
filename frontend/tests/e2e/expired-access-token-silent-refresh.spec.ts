// Spec #5: forge an invalid access token, keep the valid refresh token, reload.
// The bootstrap /api/me 401 must trigger the single-flight refresh path in
// api/client.ts, swap in a fresh access token, retry /me, and render Profile —
// all without bouncing through /login. Locks the load-bearing piece of PR #21
// against ADR-0005's chain-revoke semantics.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('an invalid access token is silently swapped via refresh and Profile still renders', async ({ page }) => {
  const username = randomUsername('refresh')
  const displayName = `Refresh Spec ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, password, displayName })
  await page.goto('/profile')
  const main = page.getByRole('main')
  await expect(main.getByRole('heading', { name: 'Profile' })).toBeVisible()

  // Sanity: refresh token is present before we tamper.
  const before = await page.evaluate(() => ({
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  }))
  expect(before.refresh).not.toBeNull()
  expect(before.access).not.toBeNull()

  // Forge a syntactically-shaped but cryptographically-invalid access token.
  // The backend rejects this with 401 → fetch wrapper kicks the refresh dance.
  await page.evaluate(() => {
    localStorage.setItem('access_token', 'forged.invalid.token')
  })

  await page.reload()

  await expect(page).toHaveURL(/\/profile$/)
  await expect(main.getByRole('heading', { name: 'Profile' })).toBeVisible()
  await expect(main.getByText(username, { exact: true })).toBeVisible()

  // The refresh path must have written a fresh access token (different from the
  // forged one). If this assertion fails, the silent-refresh wiring is broken.
  const after = await page.evaluate(() => localStorage.getItem('access_token'))
  expect(after).not.toBeNull()
  expect(after).not.toBe('forged.invalid.token')
})
