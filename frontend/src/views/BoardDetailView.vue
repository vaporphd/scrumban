<script setup lang="ts">
// Board detail view (issue #81 + add-column flow #82). First UI surface
// that consumes `BoardDetailRead.columns[]` from `GET /api/boards/{id}`
// (issue #71), and the first surface to mutate columns from the UI
// (issue #82).
//
// Five UI states driven by useBoardsStore.getById():
//  1. loading       → spinner
//  2. not-found     → "Board not found" + link back to /boards (404 branch)
//  3. error         → generic error + retry button (other non-2xx)
//  4. empty-columns → board exists but has zero columns; CTA opens the
//                     same inline add-column form used at the strip end
//  5. columns       → horizontal Trello-style strip of column cards,
//                     followed by an inline `+ Add column` card that
//                     toggles into a name-input form
//
// Layout: vanilla scoped CSS (matches BoardsListView.vue convention — there
// is no Tailwind / no shared design tokens yet). The Trello-style strip uses
// `display: flex; overflow-x: auto` so a board with many columns scrolls
// horizontally rather than wrapping or shrinking each card below readability.
//
// Task counts are intentionally placeholders ("0 tasks") for every column —
// the task list endpoint isn't shipped yet (issue #91). Once #91 lands the
// header's `column-task-count` slot will hydrate from real data; until then
// the placeholder makes the column header structure explicit so #83's
// rename / #84's delete UI all have an obvious anchor.
//
// Add-column flow (#82):
//  - Idle state: a `+ Add column` card sits at the end of the strip (or as
//    the only child when the board has zero columns; the empty-state CTA
//    text differs but the click target is the same form-trigger).
//  - Form state: the card transforms into an inline form with a single
//    name input (autofocused on transition). Enter submits, ESC cancels
//    back to idle. The store's `createColumn` action POSTs and appends the
//    returned `ColumnRead` to `currentBoard.columns` (no re-fetch — see
//    store docstring for the local-append rationale).
//  - On success: form returns to idle state with cleared input; new column
//    is already visible in the strip via the store mutation.
//  - On failure: form stays open, inline error renders, input keeps focus
//    so the user can fix and retry.
//
// Selectors:
//   - `data-testid="board-detail-loading"` — spinner branch.
//   - `data-testid="board-detail-not-found"` — 404 branch.
//   - `data-testid="board-detail-error"` — generic error branch.
//   - `data-testid="board-detail"` — root of the success branch.
//   - `data-testid="board-detail-column-{id}"` — each column card; the
//     mandatory smoke spec asserts both visible-and-ordered against this.
//   - `data-testid="board-detail-empty-columns"` — empty-columns CTA wrapper.
//   - `data-testid="board-detail-add-first-column"` — empty-state CTA button.
//   - `data-testid="add-column-trigger"` — idle "+ Add column" card.
//   - `data-testid="add-column-input"` — name input in form state.
//   - `data-testid="add-column-submit"` — explicit submit button (Enter is the
//     primary affordance per the issue acceptance, but a button is exposed for
//     pointer users).
//   - `data-testid="add-column-cancel"` — explicit cancel button (ESC is the
//     primary affordance, button exposed for pointer users).
//   - `data-testid="add-column-error"` — inline server-error message.
//   - `data-testid="add-column-validation-error"` — inline empty-name message.

import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useBoardsStore } from '@/stores/boards'
import { ApiError } from '@/types/auth'

const route = useRoute()
const boards = useBoardsStore()

// Add-column form state. `mode` controls whether the strip-end card renders
// as the idle `+ Add column` button or the inline name-input form. We keep
// the input value, validation message, and submit-error in component state
// (not store state) because they are purely UX-local — the store's
// `creatingColumn` flag is the only piece a peer flow could reasonably
// observe.
const mode = ref<'idle' | 'form'>('idle')
const name = ref('')
const validationError = ref<string | null>(null)
const submitError = ref<string | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)

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
watch(() => route.params.id, () => {
  // Reset add-column UI on board switch — the in-form state of board A
  // shouldn't bleed into board B.
  resetForm()
  loadFromRoute()
})

function retry(): void {
  loadFromRoute()
}

function resetForm(): void {
  mode.value = 'idle'
  name.value = ''
  validationError.value = null
  submitError.value = null
}

async function openForm(): Promise<void> {
  mode.value = 'form'
  // Autofocus the input on the same tick the form mounts. nextTick here
  // because the input is `v-if`d in by `mode === 'form'`, so the ref isn't
  // bound until after Vue commits the DOM update.
  await nextTick()
  nameInput.value?.focus()
}

async function onSubmit(): Promise<void> {
  if (boards.creatingColumn) return
  validationError.value = null
  submitError.value = null

  const trimmed = name.value.trim()
  if (trimmed.length === 0) {
    validationError.value = 'Name is required'
    return
  }

  if (!boards.currentBoard) {
    // Defensive — the form is only reachable from the success branch where
    // currentBoard is non-null. If we ever land here, surface a generic
    // error rather than calling the API with NaN.
    submitError.value = 'Board is not loaded'
    return
  }

  const boardId = boards.currentBoard.id
  try {
    await boards.createColumn(boardId, { name: trimmed })
    // Reset to idle on success. The new column is already in the strip
    // via the store's local append.
    resetForm()
  } catch (e) {
    if (e instanceof ApiError) {
      submitError.value = e.detail ?? e.message
    } else {
      submitError.value = (e as Error).message ?? 'Failed to create column'
    }
    // Keep focus on the input so the user can fix + retry without
    // re-clicking. nextTick to wait for the error message paint.
    await nextTick()
    nameInput.value?.focus()
  }
}

function onCancel(): void {
  if (boards.creatingColumn) return
  resetForm()
}

// Clear stale validation errors as the user types — same UX detail as the
// create-board modal. The submit-error mirrors that behavior.
watch(name, () => {
  if (validationError.value !== null) validationError.value = null
  if (submitError.value !== null) submitError.value = null
})
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

      <!--
        Empty + populated branches share the same `+ Add column` card, just
        wrapped in a different layout (the empty branch shows an explanatory
        sentence above; the populated branch lines the card up at the end of
        the strip). Both call `openForm` to flip into the inline form.
      -->
      <div
        v-if="boards.currentBoard.columns.length === 0"
        class="state-empty-columns"
        data-testid="board-detail-empty-columns"
      >
        <p>This board has no columns yet.</p>
        <div class="empty-add-column-host">
          <!-- The empty-state CTA is the same trigger as the strip-end one,
               just with an explicit "first column" label. Clicking it opens
               the form in-place and the strip renders the form card on its
               next paint (since the array is still length-0, the strip
               branch isn't rendered — we render the form here instead). -->
          <button
            v-if="mode === 'idle'"
            type="button"
            class="add-column-card add-column-trigger"
            data-testid="board-detail-add-first-column"
            @click="openForm"
          >
            + Add your first column
          </button>
          <div
            v-else
            class="add-column-card add-column-form"
          >
            <form @submit.prevent="onSubmit">
              <input
                ref="nameInput"
                v-model="name"
                type="text"
                placeholder="Column name"
                data-testid="add-column-input"
                autocomplete="off"
                maxlength="128"
                @keydown.escape.prevent="onCancel"
              />
              <p
                v-if="validationError"
                class="error"
                role="alert"
                data-testid="add-column-validation-error"
              >
                {{ validationError }}
              </p>
              <p
                v-if="submitError"
                class="error"
                role="alert"
                data-testid="add-column-error"
              >
                {{ submitError }}
              </p>
              <div class="add-column-actions">
                <button
                  type="button"
                  data-testid="add-column-cancel"
                  :disabled="boards.creatingColumn"
                  @click="onCancel"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="add-column-submit"
                  :disabled="boards.creatingColumn"
                >
                  {{ boards.creatingColumn ? 'Adding…' : 'Add column' }}
                </button>
              </div>
            </form>
          </div>
        </div>
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
        <!--
          The trailing "+ Add column" card. Same component-internal trigger
          / form pair as the empty-state branch — duplicated rather than
          factored into a child component because (a) the form's inputs
          bind into the parent's reactive state and (b) extracting it now
          would obscure the simple two-mode UX without saving any LOC
          worth speaking of.
        -->
        <li class="column add-column-host" data-testid="board-detail-add-column-host">
          <button
            v-if="mode === 'idle'"
            type="button"
            class="add-column-card add-column-trigger"
            data-testid="add-column-trigger"
            @click="openForm"
          >
            + Add column
          </button>
          <div
            v-else
            class="add-column-card add-column-form"
          >
            <form @submit.prevent="onSubmit">
              <input
                ref="nameInput"
                v-model="name"
                type="text"
                placeholder="Column name"
                data-testid="add-column-input"
                autocomplete="off"
                maxlength="128"
                @keydown.escape.prevent="onCancel"
              />
              <p
                v-if="validationError"
                class="error"
                role="alert"
                data-testid="add-column-validation-error"
              >
                {{ validationError }}
              </p>
              <p
                v-if="submitError"
                class="error"
                role="alert"
                data-testid="add-column-error"
              >
                {{ submitError }}
              </p>
              <div class="add-column-actions">
                <button
                  type="button"
                  data-testid="add-column-cancel"
                  :disabled="boards.creatingColumn"
                  @click="onCancel"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="add-column-submit"
                  :disabled="boards.creatingColumn"
                >
                  {{ boards.creatingColumn ? 'Adding…' : 'Add column' }}
                </button>
              </div>
            </form>
          </div>
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

/* Add-column card — width-matches a regular column so the strip stays even.
   Idle state uses a dashed border + lighter background to differentiate
   from a real column at a glance. Form state collapses the dashed treatment
   so the input chrome reads as the primary affordance. */
.add-column-host {
  /* The host <li> reuses .column's flex sizing so layout stays stable when
     the inner card switches between trigger and form. */
  background: transparent;
  padding: 0;
}
.empty-add-column-host {
  /* Inside the empty-state panel, host the card without the strip-style
     flex sizing — the panel already centers content. */
  width: 100%;
  max-width: 280px;
}
.add-column-card {
  width: 100%;
  min-width: 280px;
  max-width: 320px;
  border-radius: 4px;
  padding: 0.75rem;
  box-sizing: border-box;
}
.add-column-trigger {
  background: #ebecf0;
  border: 1px dashed #b3b3b3;
  color: #555;
  text-align: left;
  font-weight: 500;
  cursor: pointer;
}
.add-column-trigger:hover {
  background: #dfe1e6;
  color: #333;
}
.add-column-form {
  background: #f4f5f7;
  border: 1px solid #d0d0d0;
}
.add-column-form form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.add-column-form input {
  padding: 0.5rem;
  font: inherit;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
}
.add-column-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.error {
  color: #b00020;
  margin: 0;
  font-size: 0.85rem;
}
</style>
