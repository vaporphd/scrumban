# ADR-0004: Float Position Column for Task Ordering within Columns

**Status:** Accepted
**Date:** 2026-04-15

## Context

Tasks in a kanban column are ordered. Users reorder tasks by dragging, and every reorder is a common operation — the wire signal is `POST /api/tasks/{id}/move` with `{ column_id, after_task_id | position }`. Two common schemes:

1. **Integer `position`** — tasks have `position = 0, 1, 2, ...`. Reorder = assign a new value and shift every task between old and new position by ±1.
2. **Float `position` (lexorank-lite)** — tasks have arbitrary floats; insert between neighbours as `(prev + next) / 2`; occasionally rebalance.
3. **Linked list (`prev_id`, `next_id`)** — explicit pointers, O(1) insert, but reading ordered = traversal.

## Decision

Float `position: double precision` on `tasks`. Insertion between neighbours is `(prev + next) / 2`. A task inserted at the head uses `head - 1.0`, at the tail `tail + 1.0`. An empty column starts at `0.0`.

Periodic rebalance when the gap between any two adjacent tasks falls below a threshold (`1e-6`) or after N moves — rewrite positions as `0, 1, 2, ...` in a single transaction.

## Reasoning

- **O(1) write on reorder.** No cascading updates, no write amplification, no locking rows we didn't touch. This matters because moves are the single most common mutation in the product.
- **Simple ordering query.** `ORDER BY position ASC` with a composite index on `(column_id, position)`. Postgres handles this in its sleep.
- **Floats lose precision eventually.** IEEE 754 double has ~15–17 decimal digits; halving the gap each insert gives us roughly 50 halvings before we collide. In practice users don't do 50 inserts in the same gap without touching others — and when they do, the rebalance job handles it.
- **Not integers** because the O(n) write on every reorder makes live-sync painful: a single drag shouldn't update 30 rows.
- **Not linked list** because every board load would traverse the list, making pagination and snapshots awkward. Also: invariants like "no cycles, no orphans" are extra code.
- **Not full lexorank** (`aa`, `an`, `ao`, ...) because it's overkill; floats are simpler and we don't need the theoretically-unbounded precision lexorank provides.

## Consequences

- **`tasks(column_id, position)` composite B-tree index is mandatory.** Without it, ordered reads become sequential scans.
- **Moves must happen inside a transaction** that reads neighbour positions and writes the new one. Use `SELECT ... FOR UPDATE` on the column's affected rows if we see reorder conflicts under load; for now a default-isolation transaction is fine since collisions are rare.
- **A rebalance job** lives in the bot process alongside APScheduler (runs hourly, scans for tiny gaps). The bot process already owns scheduled work (see plan).
- **Moving across columns**: the write is still a single `UPDATE` setting `column_id` and `position` together. Reviewers should make sure these go in one transaction — a half-applied move is visible to anyone who polls the board at the wrong moment.
- **Client optimistic UI**: the frontend can compute `(prev + next) / 2` locally and send the float as part of the move request. The server can recompute and override if two clients raced.
