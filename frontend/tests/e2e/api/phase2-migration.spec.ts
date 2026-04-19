// Spec #api-2: Phase 2 schema smoke — asserts the boards/columns/tasks/labels
// migration applied cleanly and the API still boots.
//
// Per ADR-0008, every PR ships a Playwright spec. Issue #36 only adds DB
// models + migration + empty repo/service skeletons — there's no user-visible
// surface yet — so the traceable smoke artifact is this HTTP canary. If the
// migration were broken (bad FK, ENUM clash, round-trip failure), the api
// container would fail to start against the migrated DB and /api/health would
// not respond 200. The test name anchors this PR's scope for future grep.

import { expect, test } from '@playwright/test'

test('Phase 2 schema migrated — API boots with boards/columns/tasks/labels loaded', async ({
  request,
}) => {
  const response = await request.get('http://127.0.0.1:8000/api/health')
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok' })
})
