// Spec: board detail view (issue #81) — first UI surface that consumes
// `BoardDetailRead.columns[]` from `GET /api/boards/{id}` (issue #71).
//
// Mandatory smoke per ADR-0008: the page-driven scenario lives here. We
// register a fresh user via the UI, then seed the board + two columns
// directly over the API using `page.context().request` (no mocking — the
// columns endpoints landed in PR #145/#146/#148/#149 and must work
// end-to-end against the real backend, otherwise the cross-PR contract is
// already broken). Then we navigate to `/boards/:id` and assert both
// columns render in position order.
//
// Why hybrid (UI register + request setup):
//  - Register-via-UI is the existing helper pattern (`registerViaUi`); it
//    seeds tokens in localStorage, which the page's `http()` client then
//    picks up automatically. The request context inherits the page's
//    storage state, so an `Authorization` header we set explicitly maps
//    onto the same authenticated session.
//  - Request-context for board + column setup keeps the spec focused on
//    the **rendering** behavior under test. Driving the create-board modal
//    + a future add-column modal would re-test work owned by the boards
//    list spec and (eventually) the #82 add-column spec — out of scope here.
//
// Selectors: page-driven specs prefer `getByRole` / `getByText`; we use
// `getByTestId` for the column cards because the column header is an
// internal layout element with no clear accessibility role and the
// per-column id makes the assertion unambiguous (see view component).

import { expect, test } from '@playwright/test'
import { randomUsername, registerViaUi } from './helpers'

const API = 'http://127.0.0.1:8000/api'

test('register → seed board with 2 columns → /boards/:id renders both columns in order', async ({
  page,
}) => {
  const username = randomUsername('board_view')
  const displayName = `Board View Spec ${username}`
  const password = 'correct-horse-staple'

  // Step 1: register via the UI so the auth-store rehydrates and tokens
  // land in localStorage. The helper waits for the post-register
  // navigation off /register to complete.
  await registerViaUi(page, { username, displayName, password })

  // Step 2: pull the access token from localStorage and use the page's
  // request context to seed the backend directly. Inheriting from
  // `page.context().request` keeps cookies / state aligned with the page
  // (irrelevant here — auth is bearer-based — but matches the pattern
  // used by future hybrid specs).
  const accessToken = await page.evaluate(() => localStorage.getItem('access_token'))
  expect(accessToken, 'register helper should have populated access_token').not.toBeNull()
  const auth = { Authorization: `Bearer ${accessToken}` }

  const boardName = `BoardView ${username}`
  const createdBoard = await page.context().request.post(`${API}/boards`, {
    headers: auth,
    data: { name: boardName, description: 'host board for board-view smoke' },
  })
  expect(createdBoard.status()).toBe(201)
  const { id: boardId } = await createdBoard.json()

  // Two columns. Names are spec-unique (suffixed with username) so a parallel
  // worker's columns can't collide on the assertion text.
  const col1Name = `Col 1 ${username}`
  const col2Name = `Col 2 ${username}`

  const col1 = await page.context().request.post(`${API}/boards/${boardId}/columns`, {
    headers: auth,
    data: { name: col1Name },
  })
  expect(col1.status()).toBe(201)
  const { id: col1Id } = await col1.json()

  const col2 = await page.context().request.post(`${API}/boards/${boardId}/columns`, {
    headers: auth,
    data: { name: col2Name },
  })
  expect(col2.status()).toBe(201)
  const { id: col2Id } = await col2.json()

  // Step 3: navigate to /boards/:id and assert both columns render.
  await page.goto(`/boards/${boardId}`)

  // Wait for the success branch to mount before asserting — otherwise we
  // might race the loading-spinner branch.
  await expect(page.getByTestId('board-detail')).toBeVisible()

  // Each column is rendered with the per-id testid the view exposes.
  const col1Card = page.getByTestId(`board-detail-column-${col1Id}`)
  const col2Card = page.getByTestId(`board-detail-column-${col2Id}`)
  await expect(col1Card).toBeVisible()
  await expect(col2Card).toBeVisible()
  // Column header shows the name (acceptance criterion).
  await expect(col1Card).toContainText(col1Name)
  await expect(col2Card).toContainText(col2Name)
  // Task count placeholder — wired up by issue #91; currently always "0 tasks".
  await expect(col1Card).toContainText('0 tasks')

  // Order check: the issue spec calls for the columns to render in
  // position order (col1 was created first → position 1000; col2 second
  // → position 2000). We assert via the rendered DOM order. Reading
  // `data-testid` off `.column-strip > li` and comparing to the expected
  // sequence is unambiguous and survives any future style change to the
  // strip's flex direction or padding.
  const renderedIds = await page
    .getByTestId('board-detail-columns')
    .locator('> li')
    .evaluateAll((els) => els.map((el) => el.getAttribute('data-testid')))
  expect(renderedIds).toEqual([
    `board-detail-column-${col1Id}`,
    `board-detail-column-${col2Id}`,
  ])
})

test('navigating to /boards/:id for an unknown board renders the not-found branch', async ({
  page,
}) => {
  // Defensive: the view's not-found branch has its own dedicated UI
  // (separate from the generic error+retry) so a deep-linked-stale URL
  // gives the user a back-link rather than a useless retry button.
  // Backend returns 404 for an unknown board id; the store maps it to
  // the literal `'not_found'` error, which the view branches on.
  const username = randomUsername('board_view_404')
  const displayName = `Board View 404 ${username}`
  const password = 'correct-horse-staple'

  await registerViaUi(page, { username, displayName, password })

  // 9999999 is well above what the test fixtures insert. Even if a future
  // test seeds it, the not-found branch still renders only when the
  // server returns 404 — the assertion is conservative.
  await page.goto('/boards/9999999')

  await expect(page.getByTestId('board-detail-not-found')).toBeVisible()
  await expect(page.getByTestId('board-detail-not-found')).toContainText('Board not found')
  // Back link to /boards is reachable.
  await expect(page.getByRole('link', { name: /Back to boards/ })).toBeVisible()
})
