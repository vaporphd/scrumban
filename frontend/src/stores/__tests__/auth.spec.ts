import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('useAuthStore.login', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('populates state, user, and localStorage on success', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          access_token: 'a',
          refresh_token: 'r',
          token_type: 'bearer',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, {
          id: 1,
          username: 'alex',
          display_name: 'Alex',
          role: 'member',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const store = useAuthStore()
    await store.login({ username: 'alex', password: 'hunter22long' })

    expect(store.accessToken).toBe('a')
    expect(store.refreshToken).toBe('r')
    expect(store.user).toEqual({
      id: 1,
      username: 'alex',
      display_name: 'Alex',
      role: 'member',
    })
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('a')
    expect(localStorage.getItem('refresh_token')).toBe('r')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
