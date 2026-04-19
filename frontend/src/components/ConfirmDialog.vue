<script setup lang="ts">
// Reusable confirm dialog (issue #76). Same modal shell pattern as
// CreateBoardModal: focus trap, ESC cancels, backdrop click cancels, focus
// restored to the previously-focused element on unmount.
//
// Why a generic component (vs an inline confirm in BoardsListView):
// - issue #79 (delete column) will need an identical confirm dialog with a
//   danger variant; doing it inline twice would diverge in subtle ways.
// - The focus-trap + ESC-handling pattern was copied from CreateBoardModal in
//   PR #145 reviewer's feedback — making it reusable here is the cheapest way
//   to avoid a third copy.
//
// Why NOT extract focus-trap to a `useFocusTrap` composable yet:
// - Two callers (this + CreateBoardModal) is the minimum-evidence threshold
//   for "extract." With ~15 lines of trap logic per modal, the duplication
//   cost is small. Extract on the third caller (likely #79's column-delete
//   confirm if it doesn't reuse this component, or a TaskModal in Phase 2
//   later). For now the pattern is "copy the trap, scope it to modalRoot."
//
// API:
//   <ConfirmDialog
//     title="Archive this board?"
//     :body="`'${board.name}' will be hidden from the boards list.`"
//     confirm-label="Archive"
//     cancel-label="Cancel"
//     :busy="boards.archiving === board.id"
//     @confirm="onConfirm"
//     @cancel="onCancel"
//   />
//
// `confirmVariant`: 'default' (blue) | 'danger' (red). Default 'default'.
// Archive is destructive-ish but reversible; pass 'danger' for hard delete.
//
// `busy`: caller-managed disable flag for both buttons + ESC + backdrop. Used
// by the parent while the underlying mutation is in flight, so the dialog
// can't be dismissed mid-request (which would leave the user uncertain
// whether the action took).

import { onBeforeUnmount, onMounted, ref } from 'vue'

withDefaults(
  defineProps<{
    title: string
    body?: string
    confirmLabel?: string
    cancelLabel?: string
    confirmVariant?: 'default' | 'danger'
    busy?: boolean
    /** Test-id suffix so two dialogs on the same page (unlikely but possible) can be
     * disambiguated. Default `confirm-dialog`; pass `'archive-board'` for the
     * archive flow and `'delete-column'` for #79. */
    testidPrefix?: string
  }>(),
  {
    body: '',
    confirmLabel: 'Confirm',
    cancelLabel: 'Cancel',
    confirmVariant: 'default',
    busy: false,
    testidPrefix: 'confirm-dialog',
  },
)

const emit = defineEmits<{
  /** User clicked Confirm. Parent owns the mutation + closing the dialog. */
  confirm: []
  /** User pressed ESC, clicked the backdrop, or clicked Cancel. */
  cancel: []
}>()

const modalRoot = ref<HTMLElement | null>(null)
const confirmButton = ref<HTMLButtonElement | null>(null)
let previouslyFocused: HTMLElement | null = null

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
  // Focus the confirm button by default. For destructive operations a stricter
  // pattern is to focus Cancel; we don't differentiate here because the dialog
  // is single-action and the user has already opted in by clicking the row's
  // Archive button — focusing Confirm matches "press Enter to do the thing
  // I just asked for."
  confirmButton.value?.focus()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (previouslyFocused && document.contains(previouslyFocused)) {
    previouslyFocused.focus()
  }
})

function onBackdropClick(): void {
  emit('cancel')
}

function onCancel(): void {
  emit('cancel')
}

function onConfirm(): void {
  emit('confirm')
}
</script>

<template>
  <div
    ref="modalRoot"
    class="modal-backdrop"
    :data-testid="testidPrefix"
    role="dialog"
    aria-modal="true"
    aria-labelledby="confirm-dialog-title"
    @click.self="busy ? null : onBackdropClick()"
  >
    <div class="modal-card">
      <h3 id="confirm-dialog-title">{{ title }}</h3>
      <p v-if="body" class="body">{{ body }}</p>
      <div class="actions">
        <button
          type="button"
          :data-testid="`${testidPrefix}-cancel`"
          :disabled="busy"
          @click="onCancel"
        >
          {{ cancelLabel }}
        </button>
        <button
          ref="confirmButton"
          type="button"
          :data-testid="`${testidPrefix}-confirm`"
          :class="['confirm', confirmVariant]"
          :disabled="busy"
          @click="onConfirm"
        >
          {{ busy ? 'Working…' : confirmLabel }}
        </button>
      </div>
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
  width: min(24rem, 90vw);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
h3 {
  margin: 0 0 0.75rem;
}
.body {
  margin: 0 0 1rem;
  color: #333;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
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
.confirm.default {
  background: #0055aa;
  color: #fff;
  border: 1px solid #0055aa;
  border-radius: 4px;
}
.confirm.danger {
  background: #b00020;
  color: #fff;
  border: 1px solid #b00020;
  border-radius: 4px;
}
</style>
