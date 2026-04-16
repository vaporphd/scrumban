<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function onLogout(): Promise<void> {
  auth.logout()
  await router.push('/login')
}
</script>

<template>
  <section v-if="auth.user" class="profile">
    <h2>Profile</h2>
    <dl>
      <dt>ID</dt>
      <dd>{{ auth.user.id }}</dd>
      <dt>Username</dt>
      <dd>{{ auth.user.username }}</dd>
      <dt>Display name</dt>
      <dd>{{ auth.user.display_name }}</dd>
      <dt>Role</dt>
      <dd>{{ auth.user.role }}</dd>
    </dl>
    <button type="button" @click="onLogout">Log out</button>
  </section>
</template>

<style scoped>
.profile {
  max-width: 24rem;
  margin: 2rem auto;
}
dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.5rem 1rem;
  margin: 1rem 0 1.5rem;
}
dt {
  font-weight: 600;
}
dd {
  margin: 0;
}
button {
  padding: 0.5rem 1rem;
  font: inherit;
  cursor: pointer;
}
</style>
