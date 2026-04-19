<script setup lang="ts">
import { useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function onLogout(): Promise<void> {
  auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="app">
    <header>
      <h1>
        <RouterLink to="/">Scrumban</RouterLink>
      </h1>
      <nav>
        <template v-if="auth.isAuthenticated">
          <RouterLink to="/boards">Boards</RouterLink>
          <RouterLink to="/profile">{{ auth.user?.username }}</RouterLink>
          <button type="button" class="link-btn" @click="onLogout">Log out</button>
        </template>
        <template v-else>
          <RouterLink to="/login">Log in</RouterLink>
          <RouterLink to="/register">Register</RouterLink>
        </template>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  font-family: system-ui, -apple-system, sans-serif;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
}
.app {
  min-height: 100vh;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-bottom: 1px solid #e5e5e5;
}
header h1 {
  margin: 0;
  font-size: 1.25rem;
}
header h1 a {
  color: inherit;
  text-decoration: none;
}
nav {
  display: flex;
  gap: 1rem;
  align-items: center;
}
nav a {
  color: #0055aa;
  text-decoration: none;
}
nav a:hover {
  text-decoration: underline;
}
.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: #0055aa;
  cursor: pointer;
  font: inherit;
}
.link-btn:hover {
  text-decoration: underline;
}
main {
  padding: 2rem;
}
</style>
