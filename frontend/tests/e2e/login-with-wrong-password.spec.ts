// Spec #2: login with the wrong password stays on /login, shows the error,
// and never writes a token. Locks LoginView's submit-error path.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('wrong password keeps the user on /login with an error and no token', async ({ page }) => {
  const username = randomUsername('wrong')
  const password = 'correct-horse-staple'

  // Arrange: register a real user, then log out so we start from /login cleanly.
  // Both the navbar and ProfileView render a "Log out" — pick the one inside <main>.
  await registerViaUi(page, { username, password, displayName: `Wrong PW ${username}` })
  await page.goto('/profile')
  await page.getByRole('main').getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)

  // Act: submit with the right username but a wrong password.
  await page.locator('input[autocomplete="username"]').fill(username)
  await page.locator('input[autocomplete="current-password"]').fill('definitely-wrong')
  await page.getByRole('button', { name: /Sign in/ }).click()

  // Assert: error visible with non-empty text, URL still /login, no token leaked.
  // Role/text selectors over CSS classes — see tests/e2e/README.md.
  const alert = page.getByRole('alert')
  await expect(alert).toBeVisible()
  await expect(alert).not.toHaveText('')
  expect(new URL(page.url()).pathname).toBe('/login')

  const access = await page.evaluate(() => localStorage.getItem('access_token'))
  expect(access).toBeNull()
})
