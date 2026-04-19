// Pinia store for the boards list view.
//
// Responsibilities:
//  - Hold the in-memory list of boards visible to the current user.
//  - Track loading / error state for the list-fetch so the view can render
//    spinner / error+retry / empty CTA / list without owning the lifecycle.
//
// Subsequent issues (#75 create-board modal, #76/#77 detail view) will extend
// this store with `create()`, `getById()`, etc. — keep those changes additive.

import { defineStore } from 'pinia'
import { listBoardsApi } from '@/api/boards'
import { ApiError } from '@/types/auth'
import type { Board } from '@/types/boards'

interface BoardsState {
  boards: Board[]
  loading: boolean
  error: string | null
}

export const useBoardsStore = defineStore('boards', {
  state: (): BoardsState => ({
    boards: [],
    loading: false,
    error: null,
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
  },
})
