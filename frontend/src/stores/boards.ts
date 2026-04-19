// Pinia store for the boards list view.
//
// Responsibilities:
//  - Hold the in-memory list of boards visible to the current user.
//  - Track loading / error state for the list-fetch so the view can render
//    spinner / error+retry / empty CTA / list without owning the lifecycle.
//  - Expose a `create()` action that posts a new board and refreshes the list
//    on success (issue #75).
//
// Subsequent issues (#76/#77 detail view) will extend this store with
// `getById()`, etc. — keep those changes additive.

import { defineStore } from 'pinia'
import { archiveBoardApi, createBoardApi, listBoardsApi } from '@/api/boards'
import { ApiError } from '@/types/auth'
import type { Board, BoardCreate } from '@/types/boards'

interface BoardsState {
  boards: Board[]
  loading: boolean
  error: string | null
  // Separate flag for create-flow: the modal owns its own busy state and we
  // don't want a POST to flip the list view back into the spinner branch.
  creating: boolean
  // Tracks the in-flight archive's board id so a single row's button can show
  // a per-row spinner without disabling the whole list. `null` when nothing is
  // in flight. We use `id | null` (not a `boolean`) deliberately so the view
  // can scope the spinner to one row even if a future iteration permits
  // overlapping archives.
  archiving: number | null
}

export const useBoardsStore = defineStore('boards', {
  state: (): BoardsState => ({
    boards: [],
    loading: false,
    error: null,
    creating: false,
    archiving: null,
  }),
  actions: {
    async list(): Promise<void> {
      this.loading = true
      this.error = null
      try {
        this.boards = await listBoardsApi()
      } catch (e) {
        // Surface the server's `detail` when present (matches the auth-store error path).
        if (e instanceof ApiError) {
          this.error = e.detail ?? e.message
        } else {
          this.error = (e as Error).message ?? 'Failed to load boards'
        }
      } finally {
        this.loading = false
      }
    },

    /** Create a board, then re-fetch the list so the new row appears.
     *
     * Re-fetch (rather than `boards.unshift(created)`) keeps ordering /
     * archived-filter logic owned by the server — `GET /api/boards`
     * already returns newest-first and excludes archived. The modal awaits
     * this promise and closes only after success; on failure it surfaces
     * the rejected error to the caller so the form can render an inline
     * message and stay open. */
    async create(payload: BoardCreate): Promise<Board> {
      this.creating = true
      try {
        const created = await createBoardApi(payload)
        // Refresh the canonical list. We don't await this for ordering
        // reasons — listing replaces `this.boards` atomically — but we
        // do await so the view re-renders before the modal closes.
        await this.list()
        return created
      } finally {
        this.creating = false
      }
    },

    /** Archive a board, then re-fetch the list so the row disappears
     * (the default GET excludes archived boards — issue #70).
     *
     * Track the in-flight board id so the row's button can show a spinner
     * without affecting other rows. Like `create()`, we re-fetch (rather
     * than mutate `this.boards` in place) to keep the server canonical:
     * if the user races two archives or a peer archives concurrently, the
     * refetch reconciles state without bookkeeping here.
     *
     * Errors propagate to the caller so the view can show an inline message
     * (mirrors `create()`'s rejection contract). The `archiving` flag is
     * cleared in the `finally` block either way; `error` is set on failure
     * so the list view can surface it via the existing `state-error` slot. */
    async archive(id: number): Promise<void> {
      this.archiving = id
      this.error = null
      try {
        await archiveBoardApi(id)
        await this.list()
      } catch (e) {
        if (e instanceof ApiError) {
          this.error = e.detail ?? e.message
        } else {
          this.error = (e as Error).message ?? 'Failed to archive board'
        }
        throw e
      } finally {
        this.archiving = null
      }
    },
  },
})
