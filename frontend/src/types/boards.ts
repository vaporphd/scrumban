// Mirrors backend/app/domain/boards.py — BoardRead / BoardCreate. Keep in sync
// when the pydantic schemas change.
//
// The detail shape (BoardDetailRead = BoardRead + columns + labels) is intentionally
// not modeled yet — the list view (issue #74) only uses the lighter row shape.
// When the board-detail view lands (issue #76 or #77), add a `BoardDetail` interface here.

export interface Board {
  id: number
  name: string
  description: string | null
  created_by: number | null
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
  archived_at: string | null
}

// Mirrors backend `BoardCreate` (app/domain/boards.py): name 1-128 chars,
// optional description ≤4096 chars. The name length cap is enforced in the
// modal's <input maxlength> for UX; the server is the source of truth.
export interface BoardCreate {
  name: string
  description?: string | null
}
