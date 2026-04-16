// Spec #3: anonymous hit on /profile bounces to /login?next=%2Fprofile, and
// after logging in the user lands back on /profile. Locks router guard +
// LoginView's open-redirect-safe `?next=` from PR #21.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('guest is bounced to /login?next=/profile and lands on /profile after auth', async ({ browser }) => {
  // Register a user in a throwaway context so the guest-context starts empty.
  const setupContext = await browser.newContext()
  const setupPage = await setupContext.newPage()
  const username = randomUsername('guest')
  const password = 'correct-horse-staple'
  await registerViaUi(setupPage, { username, password, displayName: `Guest Spec ${username}` })
  await setupContext.close()

  // Fresh context = no tokens, no cookies, no service worker.
  const guestContext = await browser.newContext()
  const page = await guestContext.newPage()

  await page.goto('/profile')
  // Vue Router serializes the query without percent-encoding the leading slash,
  // so the URL bar shows `?next=/profile` literally. Accept either form so a
  // future router upgrade that switches to strict encoding doesn't flake the spec.
  await expect(page).toHaveURL(/\/login\?next=(\/|%2F)profile$/)

  await page.locator('input[autocomplete="username"]').fill(username)
  await page.locator('input[autocomplete="current-password"]').fill(password)
  await page.getByRole('button', { name: /Sign in/ }).click()

  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.getByRole('main').getByRole('heading', { name: 'Profile' })).toBeVisible()

  await guestContext.close()
})
