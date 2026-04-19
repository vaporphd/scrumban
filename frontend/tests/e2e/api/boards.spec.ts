// Spec #api-3: /api/boards (issues #69 + #70 + #71 + #72) — backend smoke per ADR-0008.
//
// Pure HTTP, no browser. Scenarios:
//   1. POST  /api/boards with auth → 201 + BoardRead-shaped body (issue #69).
//   2. POST  /api/boards without auth → 401 (issue #69).
//   3. GET   /api/boards without auth → 401 (issue #70).
//   4. GET   /api/boards with auth after creating two boards → both present (issue #70).
//   5. GET   /api/boards/{id} with auth → 200 + columns/labels empty arrays (issue #71).
//   6. GET   /api/boards/9999999 → 404 (issue #71).
//   7. PATCH /api/boards/{id} → 200 with new name; re-GET shows new name (issue #72).
//
// The spec mints its own user (register + login) inline. Idempotent
// across re-runs because the username is suffixed with crypto.randomUUID
// and the board name carries a timestamp; concurrent Playwright workers
// also stay collision-free.
//
// We hit the api directly on http://127.0.0.1:8000/api to mirror the
// existing `health.spec.ts` shape; the vite proxy is irrelevant for the
// `request` context.
//
// TODO(#73): once `POST /api/boards/{id}/archive` lands, extend this
// spec with the "archive one → list excludes it; ?include_archived=true
// includes it" scenario from issue #70's body. Today the archive
// service method is `NotImplementedError`, so driving the archive path
// over HTTP is impossible. The pytest suite covers both filter
// branches directly via the repo (see `backend/tests/test_boards_list.py`).

import { expect, test } from '@playwright/test'

const API = 'http://127.0.0.1:8000/api'

function uniq(prefix: string): string {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`
}

test('POST /api/boards without auth returns 401', async ({ request }) => {
  const response = await request.post(`${API}/boards`, {
    data: { name: uniq('no-auth-board'), description: 'should fail' },
  })
  expect(response.status()).toBe(401)
  expect(response.headers()['www-authenticate']).toBe('Bearer')
})

test('POST /api/boards with auth returns 201 and a BoardRead-shaped body', async ({
  request,
}) => {
  // Mint a fresh user and log in.
  const username = uniq('boards_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Boards E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  expect(typeof accessToken).toBe('string')

  // Create a board.
  const boardName = uniq('e2e-board')
  const created = await request.post(`${API}/boards`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { name: boardName, description: 'created from playwright e2e' },
  })

  expect(created.status()).toBe(201)
  const body = await created.json()

  // BoardRead shape (see backend/app/domain/boards.py):
  //   id, name, description, created_by, created_at, updated_at, archived_at
  expect(typeof body.id).toBe('number')
  expect(body.name).toBe(boardName)
  expect(body.description).toBe('created from playwright e2e')
  expect(typeof body.created_by).toBe('number')
  expect(typeof body.created_at).toBe('string')
  expect(typeof body.updated_at).toBe('string')
  expect(body.archived_at).toBeNull()
})

test('GET /api/boards without auth returns 401', async ({ request }) => {
  const response = await request.get(`${API}/boards`)
  expect(response.status()).toBe(401)
  expect(response.headers()['www-authenticate']).toBe('Bearer')
})

test('GET /api/boards returns at least the boards just inserted (containment)', async ({
  request,
}) => {
  // Mint a fresh user and log in.
  const username = uniq('boards_list_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Boards List E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  const auth = { Authorization: `Bearer ${accessToken}` }

  // Create two boards.
  const firstName = uniq('list-e2e-first')
  const secondName = uniq('list-e2e-second')
  const first = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: firstName, description: 'first' },
  })
  expect(first.status()).toBe(201)
  const second = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: secondName, description: 'second' },
  })
  expect(second.status()).toBe(201)
  const firstId = (await first.json()).id
  const secondId = (await second.json()).id

  // List boards. Other tests in this file (and concurrent workers) create
  // their own boards too, so we assert ours are present rather than
  // asserting the full list size.
  const listed = await request.get(`${API}/boards`, { headers: auth })
  expect(listed.status()).toBe(200)
  const body = await listed.json()
  expect(Array.isArray(body)).toBe(true)
  const ids = new Set(body.map((b: { id: number }) => b.id))
  expect(ids.has(firstId)).toBe(true)
  expect(ids.has(secondId)).toBe(true)

  // Both rows are non-archived (default filter excludes archived).
  const ours = body.filter((b: { id: number }) => b.id === firstId || b.id === secondId)
  for (const row of ours) {
    expect(row.archived_at).toBeNull()
  }
})

test('GET /api/boards/{id} returns 200 with empty columns and labels for a fresh board', async ({
  request,
}) => {
  // Mint a fresh user and log in.
  const username = uniq('boards_get_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Boards Get E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  const auth = { Authorization: `Bearer ${accessToken}` }

  // Create a fresh board (no columns, no labels added).
  const boardName = uniq('detail-e2e')
  const created = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: boardName, description: 'detail check' },
  })
  expect(created.status()).toBe(201)
  const { id: boardId } = await created.json()

  // GET the detail endpoint.
  const detail = await request.get(`${API}/boards/${boardId}`, { headers: auth })
  expect(detail.status()).toBe(200)
  const body = await detail.json()

  // BoardDetailRead shape (BoardRead + columns + labels). Both arrays
  // empty since we haven't seeded any columns / labels.
  expect(body.id).toBe(boardId)
  expect(body.name).toBe(boardName)
  expect(body.description).toBe('detail check')
  expect(body.archived_at).toBeNull()
  expect(Array.isArray(body.columns)).toBe(true)
  expect(body.columns).toEqual([])
  expect(Array.isArray(body.labels)).toBe(true)
  expect(body.labels).toEqual([])
})

test('PATCH /api/boards/{id} updates the name and a subsequent GET reflects it', async ({
  request,
}) => {
  // Mint a fresh user and log in.
  const username = uniq('boards_patch_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Boards PATCH E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  const auth = { Authorization: `Bearer ${accessToken}` }

  // Create a fresh board.
  const originalName = uniq('patch-e2e-original')
  const created = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: originalName, description: 'before patch' },
  })
  expect(created.status()).toBe(201)
  const { id: boardId } = await created.json()

  // PATCH the name (only). Description should stay unchanged.
  const renamed = uniq('patch-e2e-renamed')
  const patched = await request.patch(`${API}/boards/${boardId}`, {
    headers: auth,
    data: { name: renamed },
  })
  expect(patched.status()).toBe(200)
  const patchedBody = await patched.json()
  expect(patchedBody.id).toBe(boardId)
  expect(patchedBody.name).toBe(renamed)
  // description was not in the PATCH payload — must stay intact.
  expect(patchedBody.description).toBe('before patch')

  // Re-GET to prove the change is persisted, not just echoed.
  const refetched = await request.get(`${API}/boards/${boardId}`, { headers: auth })
  expect(refetched.status()).toBe(200)
  const refetchedBody = await refetched.json()
  expect(refetchedBody.id).toBe(boardId)
  expect(refetchedBody.name).toBe(renamed)
  expect(refetchedBody.description).toBe('before patch')
})

test('GET /api/boards/{id} returns 404 for an unknown id', async ({ request }) => {
  // Mint a fresh user and log in — the endpoint requires auth before
  // it can even decide on 404, so we need a valid token to trigger the
  // not-found path (an unauthenticated request would 401 first).
  const username = uniq('boards_get_404_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Boards 404 E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()

  // Use an int id that is unlikely to exist (we keep ids growing across
  // test runs; 9_999_999 is well above what these tests insert).
  const response = await request.get(`${API}/boards/9999999`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  expect(response.status()).toBe(404)
})
