<script setup lang="ts">
// Create-board modal (issue #75). First reusable modal in the codebase.
//
// Behavior:
//  - Required `name` (1-128 chars) — server is authoritative; we cap maxlength
//    + show inline "Name is required" on submit-with-blank.
//  - Optional `description` (≤4096 chars) — textarea, no min length.
//  - Submit calls `boardsStore.create(payload)` which POSTs and re-fetches the
//    list. On success we emit `created` so the parent can close us; on failure
//    we show an inline error and stay open so the user can fix and retry.
//  - ESC closes (cancel). Backdrop click closes (cancel). The Cancel button
//    is the explicit affordance. Submit is disabled while `creating`.
//  - Focus management: name input is focused on mount; ESC unwinds via the
//    `cancel` emit, which the parent uses to flip the visibility flag.
//
// We deliberately did NOT add a global toast system — the issue mentions
// "error toast on failure" but inline form errors are the simpler shape for
// the first modal in the app and keep the smoke spec deterministic. A
// project-wide toast/notification store can be added later as a separate
// PR (likely alongside issue #76+ when more flows need it) without
// breaking this contract — we'd just additionally call `toast.error(detail)`
// from the catch block here.

import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useBoardsStore } from '@/stores/boards'
import { ApiError } from '@/types/auth'

const emit = defineEmits<{
  /** User canceled (ESC, backdrop click, Cancel button). Parent should hide us. */
  cancel: []
  /** Board was created and the store list refreshed. Parent should hide us. */
  created: []
}>()

const boards = useBoardsStore()

const name = ref('')
const description = ref('')
const validationError = ref<string | null>(null)
const submitError = ref<string | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  // Focus the name field so the user can type immediately. queueMicrotask
  // is enough — the ref is bound by the time setup's onMounted fires.
  nameInput.value?.focus()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})

async function onSubmit(): Promise<void> {
  if (boards.creating) return
  validationError.value = null
  submitError.value = null

  const trimmedName = name.value.trim()
  if (trimmedName.length === 0) {
    validationError.value = 'Name is required'
    return
  }

  try {
    await boards.create({
      name: trimmedName,
      description: description.value.trim() === '' ? null : description.value.trim(),
    })
    emit('created')
  } catch (e) {
    if (e instanceof ApiError) {
      submitError.value = e.detail ?? e.message
    } else {
      submitError.value = (e as Error).message ?? 'Failed to create board'
    }
  }
}

function onBackdropClick(): void {
  if (boards.creating) return
  emit('cancel')
}

function onCancel(): void {
  if (boards.creating) return
  emit('cancel')
}
</script>

<template>
  <div
    class="modal-backdrop"
    data-testid="create-board-modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="create-board-title"
    @click.self="onBackdropClick"
  >
    <div class="modal-card">
      <h3 id="create-board-title">Create board</h3>
      <form @submit.prevent="onSubmit">
        <label>
          Name
          <input
            ref="nameInput"
            v-model="name"
            type="text"
            data-testid="create-board-name-input"
            autocomplete="off"
            maxlength="128"
            required
          />
        </label>
        <label>
          Description
          <textarea
            v-model="description"
            data-testid="create-board-description-input"
            rows="3"
            maxlength="4096"
          />
        </label>
        <p
          v-if="validationError"
          class="error"
          role="alert"
          data-testid="create-board-validation-error"
        >
          {{ validationError }}
        </p>
        <p
          v-if="submitError"
          class="error"
          role="alert"
          data-testid="create-board-submit-error"
        >
          {{ submitError }}
        </p>
        <div class="actions">
          <button
            type="button"
            data-testid="create-board-cancel"
            :disabled="boards.creating"
            @click="onCancel"
          >
            Cancel
          </button>
          <button
            type="submit"
            data-testid="create-board-submit"
            :disabled="boards.creating"
          >
            {{ boards.creating ? 'Creating…' : 'Create' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-card {
  background: #fff;
  border-radius: 8px;
  padding: 1.5rem;
  width: min(28rem, 90vw);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
h3 {
  margin: 0 0 1rem;
}
form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.9rem;
  gap: 0.25rem;
}
input,
textarea {
  padding: 0.5rem;
  font: inherit;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
}
textarea {
  resize: vertical;
  font-family: inherit;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
button {
  padding: 0.5rem 1rem;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.6;
}
.error {
  color: #b00020;
  margin: 0;
  font-size: 0.9rem;
}
</style>
