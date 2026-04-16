// Spec #6: Profile "Link Telegram" CTA generates a code; re-clicking
// invalidates the previous one. Locks issue 20 acceptance criteria.

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

test('Link Telegram CTA issues a fresh 6-digit code on each click', async ({ page }) => {
  const username = randomUsername('tglink')
  const password = 'correct-horse-staple'
  await registerViaUi(page, { username, password, displayName: `TG Link ${username}` })

  await page.goto('/profile')
  const main = page.getByRole('main')

  // Unlinked user sees the CTA. The "Link Telegram" button is the initial label;
  // after the first click it relabels to "Generate new code", so target by the
  // initial role+name here and by a regex on the second click below.
  const cta = main.getByRole('button', { name: 'Link Telegram' })
  await expect(cta).toBeVisible()

  await cta.click()
  // The code is rendered as part of `Send to bot: /start NNNNNN`; pull just the
  // 6-digit suffix so we can compare across re-issues.
  const firstCodeText = await main.getByText(/\/start \d{6}/).innerText()
  const firstMatch = firstCodeText.match(/\/start (\d{6})/)
  expect(firstMatch, 'expected /start <6-digit code> to render').not.toBeNull()
  const firstCode = firstMatch![1]

  await expect(main.getByText(/Code expires in \d+ minutes?\./)).toBeVisible()

  // After the first issuance the button relabels.
  const reissue = main.getByRole('button', { name: 'Generate new code' })
  await expect(reissue).toBeVisible()
  await reissue.click()

  // Wait for the visible code to differ from the first; if the re-issue fails
  // silently the assertion will time out instead of racing the DOM update.
  await expect.poll(async () => {
    const text = await main.getByText(/\/start \d{6}/).innerText()
    return text.match(/\/start (\d{6})/)?.[1] ?? null
  }).not.toBe(firstCode)
})
