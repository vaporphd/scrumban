// Spec #api-4: /api/boards/{id}/columns + /api/columns/{id} (issues
// #77, #78) — backend smoke per ADR-0008.
//
// Pure HTTP, no browser. Scenarios:
//   1. POST /api/boards/{id}/columns with auth on a fresh board → 201 +
//      ColumnRead-shaped body, position == 1000.
//   2. POST /api/boards/{id}/columns with an unknown board id → 404.
//   3. PATCH /api/columns/{id} renames a column; subsequent
//      GET /api/boards/{id} reflects the new name in its embedded
//      columns list (the cross-endpoint contract issue #78 locks).
//
// Later issues (#79 DELETE, #80 reorder) extend this file rather than
// fanning out into per-verb specs — keeps the columns smoke story in
// one place.
//
// The spec mints its own user (register + login) inline. Idempotent
// across re-runs because the username is suffixed with crypto.randomUUID
// and per-run data carries unique names; concurrent Playwright workers
// also stay collision-free.
//
// We hit the api directly on http://127.0.0.1:8000/api to mirror the
// existing `boards.spec.ts` shape; the vite proxy is irrelevant for the
// `request` context.

import { expect, test } from '@playwright/test'

const API = 'http://127.0.0.1:8000/api'

function uniq(prefix: string): string {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`
}

test('POST /api/boards/{id}/columns on a fresh board returns 201 with ColumnRead-shaped body', async ({
  request,
}) => {
  // Mint a fresh user and log in.
  const username = uniq('columns_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Columns E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  const auth = { Authorization: `Bearer ${accessToken}` }

  // Create a fresh board for this column.
  const boardName = uniq('columns-e2e-board')
  const createdBoard = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: boardName, description: 'host board for column smoke' },
  })
  expect(createdBoard.status()).toBe(201)
  const { id: boardId } = await createdBoard.json()

  // Append the first column.
  const columnName = uniq('todo')
  const created = await request.post(`${API}/boards/${boardId}/columns`, {
    headers: auth,
    data: { name: columnName, wip_limit: 5 },
  })

  expect(created.status()).toBe(201)
  const body = await created.json()

  // ColumnRead shape (see backend/app/domain/columns.py):
  //   id, board_id, name, position, wip_limit, created_at, updated_at
  expect(typeof body.id).toBe('number')
  expect(body.board_id).toBe(boardId)
  expect(body.name).toBe(columnName)
  // First column on a fresh board lands at COLUMN_POSITION_STEP (1000).
  // The spec asserts the literal value to lock the append-step contract
  // that issues #78/#79/#80 will reorder against.
  expect(body.position).toBe(1000)
  expect(body.wip_limit).toBe(5)
  expect(typeof body.created_at).toBe('string')
  expect(typeof body.updated_at).toBe('string')
})

test('POST /api/boards/{id}/columns with an unknown board id returns 404', async ({
  request,
}) => {
  // Mint a fresh user and log in — endpoint requires auth before it
  // can decide on 404 (an unauthenticated request would 401 first).
  const username = uniq('columns_404_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Columns 404 E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()

  // Use a board id well above what tests insert.
  const response = await request.post(`${API}/boards/9999999/columns`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { name: uniq('orphan-column') },
  })
  expect(response.status()).toBe(404)
})

test('PATCH /api/columns/{id} renames a column and the new name shows up in GET /api/boards/{id}', async ({
  request,
}) => {
  // The contract issue #78 locks: a column rename via the flat
  // /columns/{id} verb must be visible to subsequent reads of the
  // parent board (which embeds its columns via selectinload — see
  // BoardDetailRead). If the PATCH didn't commit, or if the embedded
  // columns came from a stale cache, this scenario would catch it.

  const username = uniq('columns_patch_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Columns PATCH E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()
  const auth = { Authorization: `Bearer ${accessToken}` }

  // Create a fresh board.
  const boardName = uniq('columns-patch-board')
  const createdBoard = await request.post(`${API}/boards`, {
    headers: auth,
    data: { name: boardName, description: 'host board for PATCH smoke' },
  })
  expect(createdBoard.status()).toBe(201)
  const { id: boardId } = await createdBoard.json()

  // Append a column.
  const originalName = uniq('original')
  const createdColumn = await request.post(`${API}/boards/${boardId}/columns`, {
    headers: auth,
    data: { name: originalName, wip_limit: 5 },
  })
  expect(createdColumn.status()).toBe(201)
  const { id: columnId } = await createdColumn.json()

  // PATCH the column's name (and clear wip_limit while we're at it —
  // exercises both the rename path AND the explicit-null clear path
  // in a single call).
  const renamedName = uniq('renamed')
  const patched = await request.patch(`${API}/columns/${columnId}`, {
    headers: auth,
    data: { name: renamedName, wip_limit: null },
  })
  expect(patched.status()).toBe(200)
  const patchedBody = await patched.json()
  expect(patchedBody.id).toBe(columnId)
  expect(patchedBody.name).toBe(renamedName)
  expect(patchedBody.wip_limit).toBeNull()

  // GET the parent board — its embedded columns must show the new
  // name. This is the cross-endpoint assertion the issue calls for.
  const boardAfter = await request.get(`${API}/boards/${boardId}`, {
    headers: auth,
  })
  expect(boardAfter.status()).toBe(200)
  const boardBody = await boardAfter.json()
  // BoardDetailRead embeds columns as `columns: [...]` (see
  // backend/app/domain/boards.py). Find ours by id.
  const ourColumn = boardBody.columns.find((c: { id: number }) => c.id === columnId)
  expect(ourColumn).toBeDefined()
  expect(ourColumn.name).toBe(renamedName)
  expect(ourColumn.wip_limit).toBeNull()
})

test('PATCH /api/columns/{id} with an unknown column id returns 404', async ({ request }) => {
  // Mint a user — endpoint requires auth before it can decide on 404.
  const username = uniq('columns_patch_404_e2e')
  const password = 'correct-horse-battery'

  const register = await request.post(`${API}/auth/register`, {
    data: { username, password, display_name: 'Columns PATCH 404 E2E' },
  })
  expect(register.status()).toBe(201)

  const login = await request.post(`${API}/auth/login`, {
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  const { access_token: accessToken } = await login.json()

  const response = await request.patch(`${API}/columns/9999999`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { name: uniq('orphan-rename') },
  })
  expect(response.status()).toBe(404)
})
