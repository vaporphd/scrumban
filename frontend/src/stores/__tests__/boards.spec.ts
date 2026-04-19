import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useBoardsStore } from '@/stores/boards'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('useBoardsStore.list', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('populates boards on success and clears loading/error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      jsonResponse(200, [
        {
          id: 1,
          name: 'Alpha',
          description: 'first board',
          created_by: 7,
          created_at: '2026-04-19T10:00:00Z',
          updated_at: '2026-04-19T10:00:00Z',
          archived_at: null,
        },
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    await store.list()

    expect(store.boards).toHaveLength(1)
    expect(store.boards[0]?.name).toBe('Alpha')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('captures the server detail on error and leaves boards untouched', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(500, { detail: 'boom' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    await store.list()

    expect(store.boards).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBe('boom')
  })

  it('sets loading=true while the request is in flight', async () => {
    let resolveFetch!: (response: Response) => void
    const fetchMock = vi.fn<typeof fetch>().mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    const pending = store.list()

    expect(store.loading).toBe(true)

    resolveFetch(jsonResponse(200, []))
    await pending

    expect(store.loading).toBe(false)
  })
})

describe('useBoardsStore.create', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('POSTs the payload, refreshes the list, and returns the created board', async () => {
    const created = {
      id: 42,
      name: 'My first board',
      description: 'sandbox',
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      // POST /api/boards
      .mockResolvedValueOnce(jsonResponse(201, created))
      // GET /api/boards (refresh after success)
      .mockResolvedValueOnce(jsonResponse(200, [created]))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    const result = await store.create({ name: 'My first board', description: 'sandbox' })

    expect(result).toEqual(created)
    expect(store.boards).toHaveLength(1)
    expect(store.boards[0]?.id).toBe(42)
    expect(store.creating).toBe(false)

    // Sanity-check the POST shape (URL + method + body) so a regression in the
    // api wrapper would surface here without needing a separate api spec.
    const [postUrl, postInit] = fetchMock.mock.calls[0] ?? []
    expect(postUrl).toBe('/api/boards')
    expect((postInit as RequestInit | undefined)?.method).toBe('POST')
    expect((postInit as RequestInit | undefined)?.body).toBe(
      JSON.stringify({ name: 'My first board', description: 'sandbox' }),
    )
  })

  it('rethrows on failure, clears creating, and leaves boards untouched', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(422, { detail: 'name already exists' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()

    await expect(store.create({ name: 'dup' })).rejects.toMatchObject({
      status: 422,
      detail: 'name already exists',
    })
    expect(store.boards).toEqual([])
    expect(store.creating).toBe(false)
    // No refresh should have fired on the failure path.
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
