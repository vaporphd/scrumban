<script setup lang="ts">
// Boards list view (issue #74).
//
// Four UI states driven by useBoardsStore:
//  1. loading  → spinner
//  2. error    → message + retry button
//  3. empty    → CTA "Create your first board" (opens create-board modal)
//  4. list     → render boards as router-links to /boards/{id}
//                (detail route ships in a later issue; the link will resolve
//                once /boards/:id is added — until then it 404s on click.
//                We render the link anyway so the wiring is in place.)
//
// Issue #75 added the create-board modal and wired it from two entry points:
//  - Header "New board" button (always visible while on /boards).
//  - Empty-state CTA "Create your first board" (only when boards.length === 0).
// Both flip the same `isModalOpen` ref so there's a single owner of the modal
// lifecycle. On `created` we close + the store has already refreshed the list.

import { onMounted, ref } from 'vue'
import CreateBoardModal from '@/components/CreateBoardModal.vue'
import { useBoardsStore } from '@/stores/boards'

const boards = useBoardsStore()
const isModalOpen = ref(false)

onMounted(() => {
  void boards.list()
})

function retry(): void {
  void boards.list()
}

function openModal(): void {
  isModalOpen.value = true
}

function closeModal(): void {
  isModalOpen.value = false
}
</script>

<template>
  <section class="boards">
    <header class="boards-header">
      <h2>Boards</h2>
      <button
        type="button"
        data-testid="open-create-board-modal"
        @click="openModal"
      >
        New board
      </button>
    </header>

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
      <button
        type="button"
        data-testid="create-first-board-cta"
        @click="openModal"
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

    <CreateBoardModal
      v-if="isModalOpen"
      @cancel="closeModal"
      @created="closeModal"
    />
  </section>
</template>

<style scoped>
.boards {
  max-width: 40rem;
  margin: 2rem auto;
}
.boards-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.boards-header h2 {
  margin: 0;
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
