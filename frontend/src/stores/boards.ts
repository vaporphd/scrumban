// Pinia store for the boards list view.
//
// Responsibilities:
//  - Hold the in-memory list of boards visible to the current user.
//  - Track loading / error state for the list-fetch so the view can render
//    spinner / error+retry / empty CTA / list without owning the lifecycle.
//  - Expose a `create()` action that posts a new board and refreshes the list
//    on success (issue #75).
//  - Expose a `getById()` action that fetches a single board's detail
//    (with eager-loaded columns + labels) for the board detail view
//    (issue #81). State is kept in a separate slot (`currentBoard`,
//    `currentBoardLoading`, `currentBoardError`) so navigating between
//    detail and list views does not interleave loading flags.

import { defineStore } from 'pinia'
import {
  archiveBoardApi,
  createBoardApi,
  createColumnApi,
  getBoardDetailApi,
  listBoardsApi,
} from '@/api/boards'
import { ApiError } from '@/types/auth'
import type { Board, BoardCreate, BoardDetail, Column, ColumnCreate } from '@/types/boards'

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
  // Detail view state (issue #81). Kept in its own slot so the detail-load
  // lifecycle does not collide with the list-load lifecycle — a user landing
  // on /boards/:id from a deep link shouldn't have a stale list-load error
  // bleed into their first paint of the detail page.
  currentBoard: BoardDetail | null
  currentBoardLoading: boolean
  // String for normal failures, the literal `'not_found'` for 404 so the
  // view can render a dedicated "Board not found" branch without parsing
  // the message. Server `detail` strings vary; the 404 case is the one we
  // care to special-case in the UI.
  currentBoardError: string | null
  // Separate flag for create-column-flow (issue #82). Kept distinct from
  // `creating` (board POST) and `currentBoardLoading` (detail GET) so the
  // inline `+ Add column` form has its own busy state without flipping the
  // detail view back into the spinner branch. Boolean (not `id | null`)
  // because there is at most one in-flight create-column at a time — the
  // form is single-instance, anchored at the strip end.
  creatingColumn: boolean
}

export const useBoardsStore = defineStore('boards', {
  state: (): BoardsState => ({
    boards: [],
    loading: false,
    error: null,
    creating: false,
    archiving: null,
    currentBoard: null,
    currentBoardLoading: false,
    currentBoardError: null,
    creatingColumn: false,
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
     * Error handling: failures rethrow so the caller can react (e.g. log,
     * surface a future toast). We deliberately do NOT set `this.error` here
     * — that field is reserved for list-load failures, which trigger the
     * full-page `state-error` slot. Setting it on archive failure replaced
     * the entire boards list with an error screen for what is at most a
     * single-row problem (e.g. 404 on a stale board), which was a measurably
     * jarring UX. The list stays intact; the caller decides how to surface
     * the error. A proper toast/notification system is a deferred follow-up
     * (no issue filed yet — file alongside the next flow that needs it,
     * likely #79's column-delete error UX). */
    async archive(id: number): Promise<void> {
      this.archiving = id
      try {
        await archiveBoardApi(id)
        await this.list()
      } finally {
        this.archiving = null
      }
    },

    /** Fetch a single board's detail (with embedded columns + labels) and
     * stash it on `currentBoard`. Drives the board detail view (issue #81).
     *
     * Clears `currentBoard` upfront so a navigation between two detail
     * pages doesn't briefly render the previous board's columns while the
     * new fetch is in flight. The view should branch on
     * `currentBoardLoading` first.
     *
     * 404 is surfaced as the literal `currentBoardError = 'not_found'` so
     * the view can render a dedicated "Board not found" branch with a
     * back-link, instead of a generic error+retry. Other failures land on
     * `currentBoardError` as the server `detail` string (or the raw
     * exception message for non-`ApiError` cases). */
    async getById(id: number): Promise<void> {
      this.currentBoardLoading = true
      this.currentBoardError = null
      this.currentBoard = null
      try {
        this.currentBoard = await getBoardDetailApi(id)
      } catch (e) {
        if (e instanceof ApiError) {
          this.currentBoardError = e.status === 404 ? 'not_found' : (e.detail ?? e.message)
        } else {
          this.currentBoardError = (e as Error).message ?? 'Failed to load board'
        }
      } finally {
        this.currentBoardLoading = false
      }
    },

    /** Create a column on a board and append it to the locally-cached
     * `currentBoard.columns` (issue #82). Backend assigns position as
     * `MAX(position) + 1000` (PR #147), so the new column always lands at
     * the end of the strip — appending the returned `ColumnRead` to the
     * local array matches the canonical server order without a re-fetch.
     *
     * Why local-append (not `await getById(boardId)`):
     *  - Cheaper (one POST vs POST + GET).
     *  - Avoids the brief loading-spinner flash a re-fetch would cause
     *    (currentBoardLoading flips to true, the strip vanishes, then
     *    re-renders with the new column).
     *  - The local-state-vs-server-truth divergence is bounded: the only
     *    field we synthesise is array order, and the backend's append-only
     *    position math guarantees we land in the same slot the next GET
     *    would return.
     *
     *  Phase 3 realtime will introduce the `column.created` event for
     *  cross-tab / cross-device propagation; until then, a peer's add will
     *  only show on the next manual refresh — that's the same contract as
     *  the existing boards-list flows. Filed nothing here because it's
     *  handled wholesale by the realtime subsystem.
     *
     * Guard: only mutate `currentBoard.columns` if the cached board's id
     * matches `boardId`. Without this guard a fast user-navigation between
     * /boards/A and /boards/B (with an in-flight create on A) would
     * splice A's new column into B's strip.
     *
     * Errors rethrow so the inline form can render its own message and
     * stay open. We deliberately do NOT touch `currentBoardError` — that
     * field is reserved for detail-load failures, the same separation as
     * `archive()` keeps from `error`. */
    async createColumn(boardId: number, payload: ColumnCreate): Promise<Column> {
      this.creatingColumn = true
      try {
        const created = await createColumnApi(boardId, payload)
        if (this.currentBoard && this.currentBoard.id === boardId) {
          this.currentBoard.columns.push(created)
        }
        return created
      } finally {
        this.creatingColumn = false
      }
    },
  },
})
