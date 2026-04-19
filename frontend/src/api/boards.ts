// Typed wrappers around the /api/boards endpoints.
//
// Mirrors the auth.ts pattern: thin pass-through over the shared http() client
// so JWT-bearer + 401-refresh handling is centralized in client.ts.

import type { Board } from '@/types/boards'
import { http } from './client'

export function listBoardsApi(): Promise<Board[]> {
  return http<Board[]>('/api/boards')
}
