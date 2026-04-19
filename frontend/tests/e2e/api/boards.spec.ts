// Spec #api-3: POST /api/boards (issue #69) — backend smoke per ADR-0008.
//
// Pure HTTP, no browser. Two scenarios from the issue body:
//   1. POST /api/boards with auth → 201 + BoardRead-shaped body
//   2. POST /api/boards without auth → 401
//
// The spec mints its own user (register + login) inline. Idempotent
// across re-runs because the username is suffixed with crypto.randomUUID
// and the board name carries a timestamp; concurrent Playwright workers
// also stay collision-free.
//
// We hit the api directly on http://127.0.0.1:8000/api to mirror the
// existing `health.spec.ts` shape; the vite proxy is irrelevant for the
// `request` context.

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
