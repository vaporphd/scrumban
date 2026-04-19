// Mirrors backend/app/domain/boards.py — BoardRead / BoardCreate / BoardDetailRead.
// Keep in sync when the pydantic schemas change.
//
// `Board` is the lightweight row shape used by the boards list view.
// `BoardDetail` extends `Board` with eager-loaded `columns` and `labels`,
// returned by `GET /api/boards/{id}` and consumed by the board detail view
// (issue #81). `Column` and `Label` mirror `ColumnRead` / `LabelRead`
// respectively (backend/app/domain/columns.py + labels.py).

export interface Board {
  id: number
  name: string
  description: string | null
  created_by: number | null
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
  archived_at: string | null
}

// Mirrors backend `ColumnRead` (app/domain/columns.py). `position` is the
// integer ordering key — the backend already returns columns sorted by it
// via `Board.columns` `order_by="Column.position"` (issue #71), so the
// frontend can render `board.columns` in array order without re-sorting.
export interface Column {
  id: number
  board_id: number
  name: string
  position: number
  wip_limit: number | null
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
}

// Mirrors backend `LabelRead` (app/domain/labels.py). Not consumed by the
// board detail view yet, but `BoardDetailRead.labels` is part of the payload
// so we model it for type completeness.
export interface Label {
  id: number
  board_id: number
  name: string
  color: string // `#RRGGBB` or `#RGB` per HEX_COLOR_PATTERN
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
}

// Mirrors backend `BoardDetailRead` (app/domain/boards.py): `BoardRead` plus
// eager-loaded columns (ordered by position) and labels.
export interface BoardDetail extends Board {
  columns: Column[]
  labels: Label[]
}

// Mirrors backend `BoardCreate` (app/domain/boards.py): name 1-128 chars,
// optional description ≤4096 chars. The name length cap is enforced in the
// modal's <input maxlength> for UX; the server is the source of truth.
export interface BoardCreate {
  name: string
  description?: string | null
}

// Mirrors backend `ColumnCreate` (app/domain/columns.py — see PR #145): name
// 1-128 chars, optional `wip_limit` (positive integer; null/omitted = no
// limit). Position is server-assigned (`MAX(position) + 1000`, see PR #147),
// so the client never sends it.
export interface ColumnCreate {
  name: string
  wip_limit?: number | null
}
