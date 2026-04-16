<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const displayName = ref('')
const password = ref('')
const error = ref<string | null>(null)
const submitting = ref(false)

async function submit(): Promise<void> {
  error.value = null
  submitting.value = true
  try {
    await auth.register({
      username: username.value,
      display_name: displayName.value,
      password: password.value,
    })
    await router.push('/')
  } catch (e) {
    if (e instanceof ApiError) {
      error.value = e.detail ?? e.message
    } else {
      error.value = (e as Error).message
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <h2>Create account</h2>
    <form @submit.prevent="submit">
      <label>
        Username
        <input v-model="username" type="text" autocomplete="username" required minlength="3" maxlength="64" />
      </label>
      <label>
        Display name
        <input v-model="displayName" type="text" autocomplete="name" required minlength="1" maxlength="128" />
      </label>
      <label>
        Password
        <input v-model="password" type="password" autocomplete="new-password" required minlength="8" maxlength="128" />
      </label>
      <button type="submit" :disabled="submitting">
        {{ submitting ? 'Creating…' : 'Register' }}
      </button>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p class="hint">
      Already have an account?
      <RouterLink to="/login">Log in</RouterLink>
    </p>
  </section>
</template>

<style scoped>
.auth-card {
  max-width: 22rem;
  margin: 2rem auto;
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
input {
  padding: 0.5rem;
  font: inherit;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
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
  margin-top: 0.75rem;
}
.hint {
  margin-top: 1rem;
  font-size: 0.9rem;
}
</style>
