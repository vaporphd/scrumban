<script setup lang="ts">
// Board detail view (issue #81). First UI surface that consumes
// `BoardDetailRead.columns[]` from `GET /api/boards/{id}` (issue #71).
//
// Five UI states driven by useBoardsStore.getById():
//  1. loading       → spinner
//  2. not-found     → "Board not found" + link back to /boards (404 branch)
//  3. error         → generic error + retry button (other non-2xx)
//  4. empty-columns → board exists but has zero columns; CTA stub for #82
//  5. columns       → horizontal Trello-style strip of column cards
//
// Layout: vanilla scoped CSS (matches BoardsListView.vue convention — there
// is no Tailwind / no shared design tokens yet). The Trello-style strip uses
// `display: flex; overflow-x: auto` so a board with many columns scrolls
// horizontally rather than wrapping or shrinking each card below readability.
//
// Task counts are intentionally placeholders ("0 tasks") for every column —
// the task list endpoint isn't shipped yet (issue #91). Once #91 lands the
// header's `column-task-count` slot will hydrate from real data; until then
// the placeholder makes the column header structure explicit so #82's
// add-column / #83's rename / #84's delete UI all have an obvious anchor.
//
// Selectors:
//   - `data-testid="board-detail-loading"` — spinner branch.
//   - `data-testid="board-detail-not-found"` — 404 branch.
//   - `data-testid="board-detail-error"` — generic error branch.
//   - `data-testid="board-detail"` — root of the success branch.
//   - `data-testid="board-detail-column-{id}"` — each column card; the
//     mandatory smoke spec asserts both visible-and-ordered against this.
//   - `data-testid="board-detail-empty-columns"` — empty-columns CTA.

import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useBoardsStore } from '@/stores/boards'

const route = useRoute()
const boards = useBoardsStore()

// Parse the route param. `route.params.id` is `string | string[]`; coerce to
// number and guard NaN. An invalid id is treated as a not-found — the router
// matches `/boards/:id` for any non-empty segment, so `/boards/foo` reaches
// here with `params.id = 'foo'` and we want the same dead-end UX as a 404.
function loadFromRoute(): void {
  const raw = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
  const id = Number(raw)
  if (!Number.isFinite(id) || id <= 0) {
    // Skip the network request and synthesize the not-found branch directly
    // so we don't burn a server roundtrip on obviously bad input.
    boards.currentBoard = null
    boards.currentBoardLoading = false
    boards.currentBoardError = 'not_found'
    return
  }
  void boards.getById(id)
}

onMounted(loadFromRoute)
// Re-fetch when navigating between two detail pages without unmounting (e.g.
// /boards/1 → /boards/2). vue-router reuses the component, so onMounted
// only fires for the first mount.
watch(() => route.params.id, loadFromRoute)

function retry(): void {
  loadFromRoute()
}
</script>

<template>
  <section class="board-detail">
    <div
      v-if="boards.currentBoardLoading"
      class="state-loading"
      role="status"
      aria-live="polite"
      data-testid="board-detail-loading"
    >
      <span class="spinner" aria-hidden="true"></span>
      <span>Loading board…</span>
    </div>

    <div
      v-else-if="boards.currentBoardError === 'not_found'"
      class="state-not-found"
      role="alert"
      data-testid="board-detail-not-found"
    >
      <h2>Board not found</h2>
      <p>This board does not exist or has been removed.</p>
      <RouterLink to="/boards" class="back-link">Back to boards</RouterLink>
    </div>

    <div
      v-else-if="boards.currentBoardError"
      class="state-error"
      role="alert"
      data-testid="board-detail-error"
    >
      <p class="error-message">{{ boards.currentBoardError }}</p>
      <button type="button" data-testid="board-detail-retry" @click="retry">Retry</button>
    </div>

    <div v-else-if="boards.currentBoard" class="board" data-testid="board-detail">
      <header class="board-header">
        <h2 class="board-title">{{ boards.currentBoard.name }}</h2>
        <p v-if="boards.currentBoard.description" class="board-description">
          {{ boards.currentBoard.description }}
        </p>
      </header>

      <div
        v-if="boards.currentBoard.columns.length === 0"
        class="state-empty-columns"
        data-testid="board-detail-empty-columns"
      >
        <p>This board has no columns yet.</p>
        <button type="button" data-testid="board-detail-add-first-column" disabled>
          Add your first column
        </button>
      </div>

      <ol v-else class="column-strip" data-testid="board-detail-columns">
        <li
          v-for="column in boards.currentBoard.columns"
          :key="column.id"
          class="column"
          :data-testid="`board-detail-column-${column.id}`"
        >
          <header class="column-header">
            <span class="column-name" :data-testid="`board-detail-column-${column.id}-name`">
              {{ column.name }}
            </span>
            <span
              class="column-task-count"
              :data-testid="`board-detail-column-${column.id}-task-count`"
              :title="'Task count placeholder — wired up by issue #91'"
            >
              0 tasks
            </span>
          </header>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.board-detail {
  margin: 2rem auto;
  padding: 0 1rem;
  max-width: 80rem;
}
.state-loading,
.state-error,
.state-not-found,
.state-empty-columns {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fff;
  max-width: 40rem;
  margin: 0 auto;
}
.state-loading {
  flex-direction: row;
  align-items: center;
}
.spinner {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border: 2px solid #d0d0d0;
  border-top-color: #0055aa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.error-message {
  color: #b00020;
  margin: 0;
}
.back-link {
  color: #0055aa;
  text-decoration: none;
}
.back-link:hover {
  text-decoration: underline;
}
button {
  padding: 0.5rem 1rem;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.board-header {
  margin-bottom: 1rem;
}
.board-title {
  margin: 0 0 0.25rem;
}
.board-description {
  margin: 0;
  color: #555;
  font-size: 0.95rem;
}
/* Trello-style horizontal strip. `overflow-x: auto` lets boards with many
   columns scroll sideways instead of wrapping or squishing. `align-items:
   flex-start` keeps cards top-aligned regardless of internal height. */
.column-strip {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 1rem;
  overflow-x: auto;
  /* Pad the bottom so the horizontal scrollbar doesn't crowd the last card. */
  padding-bottom: 0.5rem;
}
.column {
  flex: 0 0 auto;
  min-width: 280px;
  max-width: 320px;
  background: #f4f5f7;
  border-radius: 4px;
  padding: 0.5rem;
}
.column-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
}
.column-name {
  font-weight: 600;
}
.column-task-count {
  font-size: 0.8rem;
  color: #666;
}
</style>
