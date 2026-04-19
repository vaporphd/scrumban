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

describe('useBoardsStore.getById', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('hydrates currentBoard with the embedded columns and clears loading/error', async () => {
    // BoardDetailRead shape: BoardRead + columns[] + labels[] (see backend
    // app/domain/boards.py). We assert array-order is preserved (the backend
    // already orders by Column.position via the eager-load).
    const detail = {
      id: 5,
      name: 'Detail board',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [
        {
          id: 11,
          board_id: 5,
          name: 'Todo',
          position: 1000,
          wip_limit: null,
          created_at: '2026-04-19T10:00:00Z',
          updated_at: '2026-04-19T10:00:00Z',
        },
        {
          id: 12,
          board_id: 5,
          name: 'Done',
          position: 2000,
          wip_limit: 5,
          created_at: '2026-04-19T10:00:00Z',
          updated_at: '2026-04-19T10:00:00Z',
        },
      ],
      labels: [],
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse(200, detail))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    await store.getById(5)

    expect(store.currentBoard?.id).toBe(5)
    expect(store.currentBoard?.columns.map((c) => c.id)).toEqual([11, 12])
    expect(store.currentBoardLoading).toBe(false)
    expect(store.currentBoardError).toBeNull()

    const [getUrl, getInit] = fetchMock.mock.calls[0] ?? []
    expect(getUrl).toBe('/api/boards/5')
    expect((getInit as RequestInit | undefined)?.method ?? 'GET').toBe('GET')
  })

  it('maps a 404 to the literal "not_found" error so the view can branch on it', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(404, { detail: 'board_not_found' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    await store.getById(999)

    expect(store.currentBoard).toBeNull()
    expect(store.currentBoardError).toBe('not_found')
    expect(store.currentBoardLoading).toBe(false)
  })

  it('captures the server detail on non-404 errors and clears the previous board', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(500, { detail: 'boom' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    // Pre-seed a previous board to confirm getById clears it before the
    // request fires (no stale paint when navigating between detail pages).
    store.currentBoard = {
      id: 99,
      name: 'previous',
      description: null,
      created_by: 1,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [],
      labels: [],
    }

    await store.getById(7)

    expect(store.currentBoard).toBeNull()
    expect(store.currentBoardError).toBe('boom')
  })

  it('sets currentBoardLoading=true while the request is in flight', async () => {
    let resolveFetch!: (response: Response) => void
    const fetchMock = vi.fn<typeof fetch>().mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    const pending = store.getById(5)

    expect(store.currentBoardLoading).toBe(true)

    resolveFetch(
      jsonResponse(200, {
        id: 5,
        name: 'X',
        description: null,
        created_by: 1,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T10:00:00Z',
        archived_at: null,
        columns: [],
        labels: [],
      }),
    )
    await pending

    expect(store.currentBoardLoading).toBe(false)
  })
})

describe('useBoardsStore.createColumn', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('POSTs to the nested column endpoint, appends to currentBoard.columns, returns the created column', async () => {
    const created = {
      id: 99,
      board_id: 5,
      name: 'In Progress',
      position: 3000,
      wip_limit: null,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(201, created))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    // Pre-seed currentBoard with the same id we'll create against — exercises
    // the local-append branch (not the guard-skip branch).
    store.currentBoard = {
      id: 5,
      name: 'Board',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [
        {
          id: 11,
          board_id: 5,
          name: 'Todo',
          position: 1000,
          wip_limit: null,
          created_at: '2026-04-19T10:00:00Z',
          updated_at: '2026-04-19T10:00:00Z',
        },
      ],
      labels: [],
    }

    const result = await store.createColumn(5, { name: 'In Progress' })

    expect(result).toEqual(created)
    expect(store.currentBoard?.columns.map((c) => c.id)).toEqual([11, 99])
    expect(store.creatingColumn).toBe(false)

    const [postUrl, postInit] = fetchMock.mock.calls[0] ?? []
    expect(postUrl).toBe('/api/boards/5/columns')
    expect((postInit as RequestInit | undefined)?.method).toBe('POST')
    expect((postInit as RequestInit | undefined)?.body).toBe(
      JSON.stringify({ name: 'In Progress' }),
    )
  })

  it('skips the local append when currentBoard.id does not match boardId (cross-board guard)', async () => {
    // Defends against a fast user-navigation: an in-flight createColumn on
    // board A must not splice A's new column into board B's strip if the user
    // navigated to /boards/B before the POST resolved.
    const created = {
      id: 99,
      board_id: 5,
      name: 'Stray',
      position: 1000,
      wip_limit: null,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(201, created))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    store.currentBoard = {
      id: 999, // different from the boardId passed below
      name: 'Other Board',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [],
      labels: [],
    }

    await store.createColumn(5, { name: 'Stray' })

    // Cross-board guard: currentBoard.columns must NOT have been mutated.
    expect(store.currentBoard?.columns).toEqual([])
    expect(store.creatingColumn).toBe(false)
  })

  it('rethrows on failure, clears creatingColumn, and leaves currentBoard.columns untouched', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(422, { detail: 'name already exists' }))
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    store.currentBoard = {
      id: 5,
      name: 'Board',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [
        {
          id: 11,
          board_id: 5,
          name: 'Todo',
          position: 1000,
          wip_limit: null,
          created_at: '2026-04-19T10:00:00Z',
          updated_at: '2026-04-19T10:00:00Z',
        },
      ],
      labels: [],
    }

    await expect(store.createColumn(5, { name: 'dup' })).rejects.toMatchObject({
      status: 422,
      detail: 'name already exists',
    })
    expect(store.currentBoard?.columns.map((c) => c.id)).toEqual([11])
    expect(store.creatingColumn).toBe(false)
  })

  it('sets creatingColumn=true while the POST is in flight', async () => {
    let resolvePost!: (response: Response) => void
    const fetchMock = vi.fn<typeof fetch>().mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolvePost = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const store = useBoardsStore()
    store.currentBoard = {
      id: 5,
      name: 'Board',
      description: null,
      created_by: 7,
      created_at: '2026-04-19T10:00:00Z',
      updated_at: '2026-04-19T10:00:00Z',
      archived_at: null,
      columns: [],
      labels: [],
    }

    const pending = store.createColumn(5, { name: 'Todo' })

    expect(store.creatingColumn).toBe(true)

    resolvePost(
      jsonResponse(201, {
        id: 99,
        board_id: 5,
        name: 'Todo',
        position: 1000,
        wip_limit: null,
        created_at: '2026-04-19T10:00:00Z',
        updated_at: '2026-04-19T10:00:00Z',
      }),
    )
    await pending

    expect(store.creatingColumn).toBe(false)
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
