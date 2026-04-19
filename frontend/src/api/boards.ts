// Typed wrappers around the /api/boards endpoints.
//
// Mirrors the auth.ts pattern: thin pass-through over the shared http() client
// so JWT-bearer + 401-refresh handling is centralized in client.ts.

import type { Board, BoardCreate, BoardDetail } from '@/types/boards'
import { http } from './client'

export function listBoardsApi(): Promise<Board[]> {
  return http<Board[]>('/api/boards')
}

export function createBoardApi(payload: BoardCreate): Promise<Board> {
  return http<Board>('/api/boards', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// Idempotent: backend returns the same archived_at on repeat calls (issue #73).
// Returns the archived board so the caller can update its local row eagerly if
// it ever needs to (current `archive()` action just refetches the list).
export function archiveBoardApi(id: number): Promise<Board> {
  return http<Board>(`/api/boards/${id}/archive`, {
    method: 'POST',
  })
}

// Returns the board with eager-loaded columns (ordered by position) and labels
// (issue #71). Backed by `BoardDetailRead` server-side. The columns array is
// already sorted — render in array order without re-sorting client-side.
export function getBoardDetailApi(id: number): Promise<BoardDetail> {
  return http<BoardDetail>(`/api/boards/${id}`)
}
