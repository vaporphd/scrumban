// Tiny shared helpers for the e2e specs.
// Kept deliberately small — no fixtures, no abstractions. If a spec needs more
// than `randomUsername()`, write the steps inline so each scenario stays
// readable end-to-end without hopping into a helper module.

import type { Page } from '@playwright/test'

/** Suffix every username so concurrent runs and stale DB rows do not collide. */
export function randomUsername(prefix = 'e2e'): string {
  const suffix = crypto.randomUUID().replace(/-/g, '').slice(0, 8)
  return `${prefix}_${suffix}`
}

/** Drive the Register form end-to-end: fill, submit, wait for navigation off /register. */
export async function registerViaUi(
  page: Page,
  { username, password, displayName }: {
    username: string
    password: string
    displayName: string
  },
): Promise<void> {
  await page.goto('/register')
  await page.locator('input[autocomplete="username"]').fill(username)
  await page.locator('input[autocomplete="name"]').fill(displayName)
  await page.locator('input[autocomplete="new-password"]').fill(password)
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith('/register'), { timeout: 10_000 }),
    page.getByRole('button', { name: /Register/ }).click(),
  ])
}
