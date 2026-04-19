// Spec #api-1: tiny sanity check that the stack is alive end-to-end.
//
// Per ADR-0008, every PR ships a Playwright spec. For backend-only / DX-only
// changes like issue #67 (the pre-push env override), a pure-HTTP assertion
// using Playwright's `request` context is enough — no browser needed. It
// double-serves as a "can CI still boot the stack?" canary for DX changes
// that could silently break startup.

import { expect, test } from '@playwright/test'

test('GET /api/health returns 200 with status ok', async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8000/api/health')
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok' })
})
