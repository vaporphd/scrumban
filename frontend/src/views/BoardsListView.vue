<script setup lang="ts">
// Boards list view (issue #74). First frontend Phase 2 view.
//
// Four UI states driven by useBoardsStore:
//  1. loading  → spinner
//  2. error    → message + retry button
//  3. empty    → CTA "Create your first board" (button is a stub for now;
//                issue #75 wires it to a modal)
//  4. list     → render boards as router-links to /boards/{id}
//                (detail route ships in a later issue; the link will resolve
//                once /boards/:id is added — until then it 404s on click.
//                We render the link anyway so the wiring is in place.)

import { onMounted } from 'vue'
import { useBoardsStore } from '@/stores/boards'

const boards = useBoardsStore()

onMounted(() => {
  void boards.list()
})

function retry(): void {
  void boards.list()
}
</script>

<template>
  <section class="boards">
    <h2>Boards</h2>

    <div v-if="boards.loading" class="state-loading" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <span>Loading boards…</span>
    </div>

    <div v-else-if="boards.error" class="state-error" role="alert">
      <p class="error-message">{{ boards.error }}</p>
      <button type="button" data-testid="boards-retry" @click="retry">Retry</button>
    </div>

    <div v-else-if="boards.boards.length === 0" class="state-empty">
      <p>You don't have any boards yet.</p>
      <!-- Disabled until issue #75 wires the create-board modal. The button is
           rendered (with its data-testid) so the smoke spec's empty-state
           assertion stays meaningful, but it's a no-op with a tooltip hint
           rather than a silent live button. -->
      <button
        type="button"
        data-testid="create-first-board-cta"
        disabled
        title="Coming soon"
      >
        Create your first board
      </button>
    </div>

    <ul v-else class="board-list" data-testid="boards-list">
      <li v-for="board in boards.boards" :key="board.id" class="board-item">
        <RouterLink :to="`/boards/${board.id}`" class="board-link">
          <span class="board-name">{{ board.name }}</span>
          <span v-if="board.description" class="board-description">{{ board.description }}</span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.boards {
  max-width: 40rem;
  margin: 2rem auto;
}
h2 {
  margin: 0 0 1rem;
}
.state-loading,
.state-error,
.state-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fff;
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
button {
  padding: 0.5rem 1rem;
  font: inherit;
  cursor: pointer;
}
.board-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.board-item {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fff;
}
.board-link {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  color: inherit;
  text-decoration: none;
}
.board-link:hover {
  background: #f5f5f5;
}
.board-name {
  font-weight: 600;
}
.board-description {
  font-size: 0.85rem;
  color: #555;
}
</style>
