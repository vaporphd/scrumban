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

  it('sets creating=true while the request is in flight', async () => {
    // Mirrors the list-mid-flight pattern above (deferred-promise from PR #144
    // fix-up). Defer only the POST — we never reach the GET refresh because we
    // resolve the POST after asserting `creating===true` and then await the
    // outer promise to completion (which, via store.create → store.list, fires
    // the GET; we resolve that with a trivial empty list).
    let resolvePost!: (response: Response) => void
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockReturnValueOnce(
        new Promise<Response>((resolve) => {
          resolvePost = resolve
        }),
      )
      .mockResolvedValueOnce(jsonResponse(200, []))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    const pending = store.create({ name: 'X' })

    expect(store.creating).toBe(true)

    resolvePost(
      jsonResponse(201, {
        id: 1,
        name: 'X',
        description: null,
        created_by: 7,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T10:00:00Z',
        archived_at: null,
      }),
    )
    await pending

    expect(store.creating).toBe(false)
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

describe('useBoardsStore.archive', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('POSTs the archive, refreshes the list (which excludes the archived row), and clears archiving', async () => {
    const archived = {
      id: 7,
      name: 'Sandbox',
      description: null,
      created_by: 1,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T11:00:00Z',
      archived_at: '2026-04-19T11:00:00Z',
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      // POST /api/boards/7/archive
      .mockResolvedValueOnce(jsonResponse(200, archived))
      // GET /api/boards (refresh excludes archived; default list is empty now)
      .mockResolvedValueOnce(jsonResponse(200, []))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    await store.archive(7)

    expect(store.boards).toEqual([])
    expect(store.archiving).toBeNull()
    expect(store.error).toBeNull()

    const [postUrl, postInit] = fetchMock.mock.calls[0] ?? []
    expect(postUrl).toBe('/api/boards/7/archive')
    expect((postInit as RequestInit | undefined)?.method).toBe('POST')
  })

  it('sets archiving=<id> while the POST is in flight', async () => {
    let resolvePost!: (response: Response) => void
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockReturnValueOnce(
        new Promise<Response>((resolve) => {
          resolvePost = resolve
        }),
      )
      .mockResolvedValueOnce(jsonResponse(200, []))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    const pending = store.archive(42)

    expect(store.archiving).toBe(42)

    resolvePost(
      jsonResponse(200, {
        id: 42,
        name: 'X',
        description: null,
        created_by: 1,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T11:00:00Z',
        archived_at: '2026-04-19T11:00:00Z',
      }),
    )
    await pending

    expect(store.archiving).toBeNull()
  })

  it('rethrows on failure, clears archiving, leaves list-error untouched, and skips refresh', async () => {
    // Per the archive docstring: list-load `error` is reserved for the
    // full-page `state-error` slot, NOT for per-row mutation failures.
    // Setting it on archive failure replaced the whole list with the error
    // screen, which was jarring UX. Caller catches and decides how to
    // surface — see BoardsListView.confirmArchive.
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(404, { detail: 'board_not_found' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    // Pre-seed boards + a previous list error to prove neither is mutated by
    // the archive failure path. (Realistically `error` would be cleared by
    // the next list-load; this assertion just pins the contract: archive
    // does not touch list-load state.)
    store.boards = [
      {
        id: 1,
        name: 'Untouched',
        description: null,
        created_by: 1,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T10:00:00Z',
        archived_at: null,
      },
    ]
    store.error = 'previous list error'

    await expect(store.archive(999)).rejects.toMatchObject({
      status: 404,
      detail: 'board_not_found',
    })
    expect(store.archiving).toBeNull()
    // List-error untouched; the seeded boards array untouched.
    expect(store.error).toBe('previous list error')
    expect(store.boards).toHaveLength(1)
    // No refresh fires when archive POST fails.
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
