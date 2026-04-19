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

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
// Root element of the modal — used by the focus trap to enumerate focusable
// descendants. Bound via the template ref below.
const modalRoot = ref<HTMLElement | null>(null)
// Element that had focus before the modal mounted, so we can restore it on
// unmount. Without this, focus returns to <body> after a modal close, which
// is a measurable a11y regression for keyboard users.
let previouslyFocused: HTMLElement | null = null

// Selectors for "things a Tab keypress can land on inside the modal." Kept
// narrow on purpose — anchors / form fields / buttons / explicit tabindex
// cover everything we render today and almost every modal we'll add. If a
// future modal embeds an iframe or contenteditable region, extend this list.
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'textarea:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function focusableElements(): HTMLElement[] {
  if (!modalRoot.value) return []
  return Array.from(modalRoot.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (event.key === 'Tab') {
    // Focus trap: keep keyboard focus inside the modal. First reusable modal
    // in the codebase, so the pattern propagates to #76+ — keep it minimal
    // (no 3rd-party dep) but correct (handles shift+tab and the empty-list
    // edge case).
    const focusables = focusableElements()
    if (focusables.length === 0) {
      event.preventDefault()
      return
    }
    const first = focusables[0]!
    const last = focusables[focusables.length - 1]!
    const active = document.activeElement as HTMLElement | null
    if (event.shiftKey) {
      if (active === first || !modalRoot.value?.contains(active)) {
        event.preventDefault()
        last.focus()
      }
    } else {
      if (active === last || !modalRoot.value?.contains(active)) {
        event.preventDefault()
        first.focus()
      }
    }
  }
}

onMounted(() => {
  previouslyFocused = (document.activeElement as HTMLElement | null) ?? null
  window.addEventListener('keydown', onKeydown)
  // Focus the name field so the user can type immediately. queueMicrotask
  // is enough — the ref is bound by the time setup's onMounted fires.
  nameInput.value?.focus()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  // Restore focus to whatever had it before we opened. Guard against the
  // element having been removed from the DOM in the interim.
  if (previouslyFocused && document.contains(previouslyFocused)) {
    previouslyFocused.focus()
  }
})

// Clear a stale submit error as soon as the user starts editing the name —
// otherwise a "name too long" message persists after they shorten the input,
// which is confusing. Description is a free-form field with no server-side
// uniqueness rules so we don't bother mirroring the watcher there.
watch(name, () => {
  if (submitError.value !== null) submitError.value = null
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
    ref="modalRoot"
    class="modal-backdrop"
    data-testid="create-board-modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="create-board-title"
    @click.self="onBackdropClick"
  >
    <div class="modal-card">
      <h3 id="create-board-title">Create board</h3>
      <!-- novalidate: we own the validation UX in JS so the inline error message
           ("Name is required") is testable and consistent across browsers.
           The HTML5 `required` attribute on the name input is kept as a semantic
           marker but native popovers are suppressed. -->
      <form novalidate @submit.prevent="onSubmit">
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
